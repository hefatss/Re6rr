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
  0x140c50d80  play3DSeLoop: request 0, two xyz triples into the 0xa0 voice
               request via nuSound2_3DKeySetOnHandle
  0x140c52100  BGM play: nuSound2StreamStartEx(handle 0, path, 0) via playStream
  0x18002c2b0  nuSound2 voice params: 64 slots of 0xa0, meta at 0x2800+slot*0xc
  0x1800237d0  builds the 0xa0 voice request: pointers at +0x10/+0x18/+0x20,
               volume/pan/flags at +0x84/+0x88/+0x8c, defaults from 0x1800011b0
  0x18002eb80  bank-slot setup: 64 slots of 0x804, voice ids at +0x46
  0x18001cbc0  68 mixer buses of 0x48; nuSound2BusFade fades over N frames
  0x180020290  piecewise dB -> volume; 0x1800201b0 inverse, calibration at
               instance +0x1c20/+0x1c28/+0x1c2c
  0x18034fc0  nuSound2_3DSetConfig parses config_3d.bin: 5 sections of 0x130,
               10 records of 0x1c, dB -> amplitude at 0x1800274d0
   0x1407d674d  SoundManager ctor builds the 0x28-byte Sound::Initialize config:
                bankNum 8, reqidNum 0x22, streamNum 1, two config pointers
   0x140c53c20  sys::Sound::Initialize -> Impl ctor 0x140c533c0; 0x98-byte Impl
   0x18029a60  nuSound2InitEx reads config +0x20 as bnusCoreInitEx argument

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

# nuSound2 mixer: 68 buses of 0x48 bytes (FUN_18001cbc0), fade fields relative
# to the bus base (FUN_18001cbc0 / nuSound2BusSetVol / nuSound2BusFade).
BUS_COUNT = 0x44
BUS_STRIDE = 0x48
BUS_MODE_OFFSET = 0x10
BUS_VOLUME_OFFSET = 0x00
BUS_TARGET_OFFSET = 0x18
BUS_STEP_OFFSET = 0x1C
BUS_FRAME_OFFSET = 0x14
BUS_FADE_MODE = 2
BUS_INVALID = 0x80000001
# Piecewise dB <-> linear volume calibration at instance +0x1c20/28/2c.
DB_CALIBRATION_OFFSETS = (0x1C20, 0x1C28, 0x1C2C)

# FUN_1800237d0 builds the 0xa0 voice request from the KeyOn arguments;
# FUN_1800011b0 sets defaults for the six floats at +0x84.
VOICE_REQUEST_FIELDS = {
    "request": (0x00, 4), "bank": (0x04, 4), "bank_info": (0x08, 4),
    "tone": (0x0C, 4), "bank_ptr": (0x10, 8), "tone_ptr": (0x18, 8),
    "voice_ptr": (0x20, 8), "chain_tone": (0x28, 4), "extended": (0x2C, 4),
    "reserved": (0x30, 4), "ext_a": (0x34, 0x34), "ext_b": (0x68, 0x1C),
    "volume": (0x84, 4), "pan": (0x88, 4), "flags": (0x8C, 4),
    "extra_a": (0x90, 4), "extra_b": (0x94, 4), "extra_c": (0x98, 4),
}
VOICE_FLOAT_DEFAULTS = (1.0, 0.0, 0, 0.0, 1.0, 1.0)

# sys::Sound::Impl::play3DSeLoop (0x140c50d80) -> nuSound2_3DKeySetOnHandle.
PLAY_3D_SE_LOOP = {
    "function": 0x140C50D80, "request": 0, "volume": 0.0, "pan": 0.0,
    "slot_stride": 8, "flag_offset": 0, "tone_offset": 4,
    "vectors": 2, "vector_floats": 3,
    "wrapper": 0x180363B0,
    "wrapper_errors": {"null_secondary": 0x80000031,
                       "null_third": 0x80000032, "null_position": 0x80000033},
}


# sys::Sound::Initialize (0x140c53c20) takes a 0x28-byte config. SoundManager's
# ctor fills it at 0x1407d674d; the Impl ctor (0x140c533c0) validates the three
# counts and sizes the three vectors. nuSound2InitEx passes config +0x20 to
# bnusCoreInitEx (0x18001c9e0).
INIT_CONFIG_WRITE_VA = 0x1407D674D
INIT_CONFIG_BYTES = bytes.fromhex(
    "c745d708000000" "c745db22000000" "c745df01000000")
SOUND_INIT = {
    "config_size": 0x28,
    "bank_num": {"offset": 0x00, "value": 8, "max": 0x10},
    "reqid_num": {"offset": 0x04, "value": 0x22, "max": 0x100},
    "stream_num": {"offset": 0x08, "value": 1, "min": 1, "max": 0x10},
    "config_bin": 0x10,
    "config_3d_bin": 0x18,
    "core_init": 0x20,
    "impl": {
        "size": 0x98,
        "banks": {"offset": 0x00, "stride": 0x20},
        "requests": {"offset": 0x20, "stride": 0x08},
        "streams": {"offset": 0x40, "stride": 0x10},
        "stream_buffer_size": 0xAC440,
        "output_mode": 4,
        "zero_quad_offset": 0x60,
        "volume_offsets": (0x80, 0x88),
        "sentinel_offset": 0x90,
    },
}


def sound_init_facts(pe):
    """Return the Sound::Initialize ABI, grounded in the shipped constants."""
    off = pe.off(INIT_CONFIG_WRITE_VA - pe.image_base)
    if off is None or pe.raw[off:off + len(INIT_CONFIG_BYTES)] != \
            INIT_CONFIG_BYTES:
        raise ValueError("Sound::Initialize config constants not found")
    return SOUND_INIT


def voice_request(request, bank, tone, bank_info=0, bank_ptr=0, tone_ptr=0,
                  voice_ptr=0, chain_tone=-1, extended=0, ext_a=b"",
                  ext_b=b"", volume=None, pan=None, flags=None,
                  extra_a=None, extra_b=None, extra_c=None):
    """Build the 0xa0 record passed to FUN_18002c2b0."""
    values = [volume, pan, flags, extra_a, extra_b, extra_c]
    floats = [VOICE_FLOAT_DEFAULTS[index] if value is None else value
              for index, value in enumerate(values)]
    record = bytearray(VOICE_RECORD_STRIDE)
    struct.pack_into("<iiiIQQQiiI", record, 0, request, bank, bank_info,
                     tone, bank_ptr, tone_ptr, voice_ptr, chain_tone,
                     extended, 0)
    offset = VOICE_REQUEST_FIELDS["ext_a"][0]
    for blob, width in ((ext_a, 0x34), (ext_b, 0x1C)):
        if len(blob) > width:
            raise ValueError("voice extension too long")
        record[offset:offset + len(blob)] = blob
        offset += width
    struct.pack_into("<ffIfff", record, VOICE_REQUEST_FIELDS["volume"][0],
                     float(floats[0]), float(floats[1]), int(floats[2]),
                     float(floats[3]), float(floats[4]), float(floats[5]))
    return record


def decibels_to_volume(db, lo, mid, hi):
    """FUN_180020290: piecewise-linear dB -> volume with runtime calibration."""
    if db <= lo:
        return 0.0
    if db < mid:
        return hi / (mid - lo) * (db - lo)
    return (hi - 1.0) / mid * db + 1.0


def volume_to_decibels(volume, lo, mid, hi):
    """FUN_1800201b0: inverse of `decibels_to_volume`."""
    if volume <= 0.0:
        return lo
    if volume <= hi:
        return (mid - lo) / hi * volume + lo
    return mid / (hi - 1.0) * (volume - 1.0)


def bus_fade(state, target, frames):
    """nuSound2BusFade: immediate set for frames < 1, else linear step."""
    if frames < 1:
        state["volume"] = target
        state["step"] = 0.0
        state["mode"] = 0
        state["frames"] = 0
    else:
        state["target"] = target
        state["step"] = (target - state["volume"]) / float(frames)
        state["frames"] = frames
        state["mode"] = BUS_FADE_MODE
    return state


CONFIG_3D_VERSION = (1, 2, 3)
CONFIG_3D_SECTION_STRIDE = 0x130
CONFIG_3D_RECORD_STRIDE = 0x1C
CONFIG_3D_RECORD_COUNT = 10
CONFIG_3D_TAIL_OFFSET = 0x118
CONFIG_3D_TAIL_COUNT = 6
DB_TO_AMPLITUDE_SCALE = 0.115129255  # ln(10)/20, from FUN_1800274d0


def decibels_to_amplitude(db, zero_db):
    """FUN_1800274d0: 10^(db/20) above the runtime zero-dB floor."""
    if db <= zero_db:
        return 0.0
    return 10.0 ** (db * DB_TO_AMPLITUDE_SCALE)


def parse_config_3d(raw):
    """nuSound2_3DSetConfig / FUN_180032520: parse config_3d.bin."""
    if len(raw) < 0x20:
        raise ValueError("short config_3d header")
    if tuple(raw[4:7]) != CONFIG_3D_VERSION:
        raise ValueError("config_3d version")
    count, stride = struct.unpack_from("<ii", raw, 8)
    if stride != CONFIG_3D_SECTION_STRIDE or not 0 <= count <= 0x20:
        raise ValueError("config_3d layout")
    if 0x20 + count * stride > len(raw):
        raise ValueError("config_3d size")
    floats = struct.unpack_from("<4f", raw, 0x10)
    sections = []
    for index in range(count):
        base = 0x20 + index * stride
        records = []
        for record in range(CONFIG_3D_RECORD_COUNT):
            offset = base + record * CONFIG_3D_RECORD_STRIDE
            values = struct.unpack_from("<I3f3I", raw, offset)
            records.append({
                "flags": values[0], "db_start": values[1],
                "angle": values[2] + 90.0, "db_end": values[3],
                "raw": list(values[4:]),
            })
        tail = struct.unpack_from("<%dI" % CONFIG_3D_TAIL_COUNT, raw,
                                  base + CONFIG_3D_TAIL_OFFSET)
        sections.append({"records": records, "tail": list(tail)})
    return {"version": CONFIG_3D_VERSION, "count": count,
            "stride": stride, "floats": floats, "sections": sections}


def mixer_facts():
    return {
        "bus_count": BUS_COUNT, "bus_stride": BUS_STRIDE,
        "fields": {"mode": BUS_MODE_OFFSET, "volume": BUS_VOLUME_OFFSET,
                   "target": BUS_TARGET_OFFSET, "step": BUS_STEP_OFFSET,
                   "frames": BUS_FRAME_OFFSET},
        "fade_mode": BUS_FADE_MODE, "invalid_bus": BUS_INVALID,
        "db_calibration": DB_CALIBRATION_OFFSETS,
    }

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
        "play_3d_se_loop": PLAY_3D_SE_LOOP,
        "playback": {
            "bgm_stream_handle": BGM_STREAM_HANDLE,
            "voice_slots": VOICE_SLOT_COUNT,
            "voice_stride": VOICE_RECORD_STRIDE,
            "voice_meta_base": VOICE_META_BASE,
            "voice_meta_stride": VOICE_META_STRIDE,
            "bank_set_errors": BANK_SET_ERRORS,
            "request_fields": VOICE_REQUEST_FIELDS,
            "float_defaults": VOICE_FLOAT_DEFAULTS,
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
        "sound_init": sound_init_facts(pe),
        "mixer": mixer_facts(),
        "config_3d": parse_config_3d(open(os.path.join(dump, "data", "sound",
                                                "config_3d.bin"), "rb").read()),
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
