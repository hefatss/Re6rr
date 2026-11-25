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
  0x140c50740  six-argument playSe: nuSound2KeySetOnHandle(bank handle, tone,
               volume, pan, flags, &key); readyBank checks state 3 at +0x1c
  0x140c50ac0  playSeLoop: 8-byte loop records, request id 0x21 used by scene
  0x1401aebc0  positional SE records of 0x24 bytes (bank, tone, frames, xyz)
  0x140c52100  BGM play: nuSound2StreamStartEx(handle 0, path, 0) via playStream
  0x18002c2b0  nuSound2 voice params: 64 slots of 0xa0, meta at 0x2800+slot*0xc
  0x18002eb80  bank-slot setup: 64 slots of 0x804, voice ids at +0x46

No shipped table maps arbitrary game events to (bank, tone); those pairs stay
native call-site constants, not invented data. No shipped Lua file calls any of
the 12 bindings above.
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

# Sound dispatch ABI recovered from sys::Sound::Impl and nuSound2 exports.
BANK_STRIDE = 0x20
BANK_HANDLE_OFFSET = 0x18
BANK_STATE_OFFSET = 0x1C
BANK_STATE_READY = 3
REQUEST_COUNT = 0x22
LOOP_SLOT_SCENE = 0x21
LOOP_RECORD_STRIDE = 8
POSITIONAL_SE_STRIDE = 0x24
KEYON_DEFAULTS = {"volume": 1.0, "pan": 0.0, "flags": 0,
                  "extra": [0.0, 1.0, 1.0]}
BGM_STREAM_HANDLE = 0
VOICE_SLOT_COUNT = 0x40
VOICE_RECORD_STRIDE = 0xA0
VOICE_META_BASE = 0x2800
VOICE_META_STRIDE = 0xC
# FUN_18002eb80 bank-slot errors, keyed by the value returned to the caller.
BANK_SET_ERRORS = {"bad_index": 0x8000001E, "bad_format": 0x8000001D,
                   "null_data": 0x80000024, "already_set": 0x80000021,
                   "voice_fail": 0x80000026, "stream_fail": 0x80000027}

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


def config_header(dump):
    """Parse the six (count, offset) pairs in data/sound/config.bin."""
    path = os.path.join(dump, SOUND, "config.bin")
    with open(path, "rb") as stream:
        raw = stream.read()
    if raw[:4] != b"nusc" or raw[4:8] != b"\x01\x02\x03\x00":
        raise ValueError("unexpected config.bin header")
    size, header_size = struct.unpack_from("<II", raw, 8)
    if size != len(raw) or header_size != 0x50:
        raise ValueError("config.bin size/header mismatch")
    float_offset, = struct.unpack_from("<I", raw, 0x14)
    # 0x18 onward: six (count, offset) pairs; 0x14 is the float-block offset.
    pairs = [struct.unpack_from("<II", raw, 0x18 + index * 8)
             for index in range(6)]
    return {"size": size, "header_size": header_size,
            "float_offset": float_offset, "sections": pairs}


def dispatch_facts(dump):
    config = config_header(dump)
    return {
        "bank_table": {"stride": BANK_STRIDE, "handle": BANK_HANDLE_OFFSET,
                       "state": BANK_STATE_OFFSET, "ready": BANK_STATE_READY},
        "requests": {"count": REQUEST_COUNT, "loop_slot": LOOP_SLOT_SCENE,
                     "loop_stride": LOOP_RECORD_STRIDE,
                     "positional_stride": POSITIONAL_SE_STRIDE},
        "key_on_defaults": KEYON_DEFAULTS,
        "playback": {
            "bgm_stream_handle": BGM_STREAM_HANDLE,
            "voice_slots": VOICE_SLOT_COUNT,
            "voice_stride": VOICE_RECORD_STRIDE,
            "voice_meta_base": VOICE_META_BASE,
            "voice_meta_stride": VOICE_META_STRIDE,
            "bank_set_errors": BANK_SET_ERRORS,
        },
        "config": config,
    }


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
        "dispatch": dispatch_facts(dump),
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
    dispatch = sections["dispatch"]
    print("requests: %d, scene loop slot: 0x%x, config sections: %s" %
          (dispatch["requests"]["count"], dispatch["requests"]["loop_slot"],
           dispatch["config"]["sections"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
