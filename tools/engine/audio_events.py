"""Recover shipped BGM ids and Lua/SE sound bindings from wmn6r.exe.

    python tools/engine/audio_events.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/audio_events.json

Native evidence (VA in `wmn6r.exe`, image base 0x140000000):

  0x141e1f8e0  142 pointers to `./data/sound/BGM/*.nub` (BGM id -> path)
  0x1414ec550  142 fixed 0x40-byte strings, same id order (BGM id -> name)
  0x1407cc8b0  id -> path pointer; 0x1407cc8c0 name -> id (substring match)
  0x1407d6940  playBGM: id 0x8c stops, 0x8d logs BGM_RANDOM error
  0x140c50580  playSe(bank, tone): bank table stride 0x20, handle at +0x18,
               calls nuSound2KeyOnHandle(handle, tone, 0)

Lua bindings live in the `luaL_Reg` table at VA 0x141e1a070 and call
`FUN_140c51f80` / `FUN_140c51fa0` / `FUN_140c52010` / `FUN_140c52050`.
`PlaySE` hardcodes bank 2 (SYSTEM); `PlaySEOfBank` takes the bank id.
No shipped table maps arbitrary game events to (bank, tone); those pairs stay
native call-site constants, not invented data.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
from pe_report import PE  # noqa: E402

SOUND = os.path.join("data", "sound")
BGM_NAME_VA = 0x1414EC550
BGM_PATH_VA = 0x141E1F8E0
BGM_COUNT = 142
BGM_NAME_STRIDE = 0x40
BGM_NO_SOUND = 0x8C
BGM_RANDOM = 0x8D

# Lua name -> function VA, native call form, fixed bank/tone where present.
BINDINGS = {
    "PlaySE": (0x1407815D0, "playSe", 2, None),
    "PlaySEOfBank": (0x140781650, "playSe", None, None),
    "PlaySELoop": (0x140781740, "playSeLoop", 2, None),
    "PlaySELoopOfBank": (0x140781830, "playSeLoop", None, None),
    "StopSELoop": (0x140781990, "stopSeLoop", None, None),
    "PlaySEDecide": (0x140781A10, "playSe", 2, 0x2F),
    "PlaySECancel": (0x140781A40, "playSe", 2, 0x07),
    "PlaySEMove": (0x140781A70, "playSe", 2, 0x0F),
    "PlayBGM": (0x140781AA0, "playBgm", None, None),
    "PlayBGMByName": (0x140781B20, "playBgmByName", None, None),
    "FadeOutBGM": (0x140781BA0, "fadeOutBgm", None, None),
    "StopBGM": (0x140781CA0, "stopBgm", None, None),
}


def cstr(data, offset, size=None):
    limit = len(data) if size is None else min(len(data), offset + size)
    end = data.find(b"\0", offset, limit)
    if end < 0:
        end = limit
    return data[offset:end].decode("latin1")


def bank_names(dump):
    raw = open(os.path.join(dump, SOUND, "nuSound2BankStr.bin"), "rb").read()
    count = struct.unpack_from("<I", raw, 4)[0]
    names = []
    for index in range(count):
        offset = 0x10 + index * 0x30
        bank_id, = struct.unpack_from("<Q", raw, offset)
        names.append((bank_id, cstr(raw, offset + 0x10, 0x20)))
    return names


def tone_names(dump, bank):
    raw = open(os.path.join(dump, SOUND, "nuSound2ToneStr%s.bin" % bank),
               "rb").read()
    count, = struct.unpack_from("<I", raw, 8)
    result = []
    for index in range(count):
        offset = 0x40 + index * 0x80
        result.append((cstr(raw, offset, 0x40),
                       cstr(raw, offset + 0x40, 0x40)))
    return result


def bgm_table(pe):
    off = pe.off(BGM_PATH_VA - pe.image_base)
    if off is None:
        raise ValueError("BGM path table VA 0x%x is not mapped" % BGM_PATH_VA)
    pointers = struct.unpack_from("<%dQ" % BGM_COUNT, pe.raw, off)
    off = pe.off(BGM_NAME_VA - pe.image_base)
    if off is None:
        raise ValueError("BGM name table VA 0x%x is not mapped" % BGM_NAME_VA)
    names = pe.raw[off:off + BGM_COUNT * BGM_NAME_STRIDE]
    result = []
    for index, pointer in enumerate(pointers):
        path = pe.cstr(pointer - pe.image_base)
        name = cstr(names, index * BGM_NAME_STRIDE, BGM_NAME_STRIDE)
        result.append({"id": index, "name": name, "path": path})
    return result


def bgm_by_name(table, name):
    for row in table:
        if name in row["name"]:
            return row["id"]
    return -1


def resolved_bindings(dump):
    banks = dict(bank_names(dump))
    rows = []
    for name, (address, kind, bank, tone) in BINDINGS.items():
        rows.append({
            "name": name,
            "address": address,
            "call": kind,
            "bank": bank,
            "bank_name": banks.get(bank) if bank is not None else None,
            "tone": tone,
            "tone_name": None,
        })
    cache = {}
    for row in rows:
        key = row["bank"]
        if key is None or row["tone"] is None:
            continue
        if key not in cache:
            cache[key] = dict((index, (tone, wav)) for index, (tone, wav)
                              in enumerate(tone_names(dump, banks[key])))
        entry = cache[key].get(row["tone"])
        if entry:
            row["tone_name"], row["wav"] = entry
    return rows


def build(dump):
    pe = PE(os.path.join(dump, "wmn6r.exe"))
    return {
        "banks": bank_names(dump),
        "bgm": bgm_table(pe),
        "bindings": resolved_bindings(dump),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", help="write JSON report")
    args = parser.parse_args()

    sections = build(args.dump)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf8") as stream:
            json.dump(sections, stream, indent=2, ensure_ascii=False)
    print("banks: %d, bgm ids: %d, Lua sound bindings: %d" %
          (len(sections["banks"]), len(sections["bgm"]),
           len(sections["bindings"])))
    for row in sections["bindings"][:8]:
        print("  %-14s %-12s bank %-4s tone %-5s %s" %
              (row["name"], row["call"], row["bank_name"] or "-",
               row["tone"] if row["tone"] is not None else "-",
               row["tone_name"] or ""))
    for index in (0, BGM_NO_SOUND, BGM_RANDOM):
        row = sections["bgm"][index]
        print("  bgm %3d %-24s %s" % (index, row["name"], row["path"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
