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
  0x18002eb80  bank-slot setup: 64 slots of 0x804, voice ids at +0x46;
                version bytes 0..2 must be 1,2,1
  0x18002f1c0  bank register: 64 slots of 0x804, state pointer at slot +0x42
  0x18002e1b0  tone record = bank + *(u32 *)(bank + 0x18 + tone*4); +0x18 is
               the offset-table base (0x20), +0x1c the first record offset
  0x180026a60  chained KeyOn: up to 32 voices, 0xd0-byte state records at
               instance +0x21c (0x180025b80 builds, 0x180029220 applies)
  0x180035b80  stream byte reservation at instance +0x80508, cap 0x20000000
  0x18001cbc0  68 mixer buses of 0x48; nuSound2BusFade fades over N frames
  0x180020290  piecewise dB -> volume; 0x1800201b0 inverse, calibration at
               instance +0x1c20/+0x1c28/+0x1c2c
  0x18034fc0  nuSound2_3DSetConfig parses config_3d.bin: 5 sections of 0x130,
               10 records of 0x1c, dB -> amplitude at 0x1800274d0
   0x1407d674d  SoundManager ctor builds the 0x28-byte Sound::Initialize config:
                bankNum 8, reqidNum 0x22, streamNum 1, two config pointers
   0x140c53c20  sys::Sound::Initialize -> Impl ctor 0x140c533c0; 0x98-byte Impl
   0x18029a60  nuSound2InitEx reads config +0x20 as bnusCoreInitEx argument
   0x1800237d0  extended KeyOn: memcpy 0x34/0x1c bytes from two pointers only
                when both are non-null; 3D wrappers are the shipped users
   0x1407d6940  playBGM: current/next ids at +0x44c/+0x450; 0x8c stops via fade
   0x180016850  nuSound2StreamFadeOut: fade frames/step at stream +0x298/+0x29c

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
                   "byte0_mismatch": 0x80000042, "no_slot": 0x8000001B,
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
    "wrapper": 0x1800363B0,
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


# FUN_18001a4e0 is memcpy. FUN_180026a60 sets its extended flag only when both
# extension pointers are non-null; FUN_1800237d0 then copies them into the voice
# request at +0x34 (0x34 bytes) and +0x68 (0x1c bytes). The 6-argument game
# wrappers pass null pointers; play3DSeLoop passes three vectors through
# nuSound2_3DKeySetOnHandle -> ...Chgrp, so the shipped extended users are 3D.
EXTENDED_KEY_ON = {
    "memcpy": 0x18001A4E0,
    "layer": 0x1800237D0,
    "activator": 0x180026A60,
    "flag": "both_extension_pointers_non_null",
    "blobs": {"a": {"request_offset": 0x34, "size": 0x34},
              "b": {"request_offset": 0x68, "size": 0x1C}},
    "chain": {"last_tone_offset": 0x2C, "error": 0x8000004B,
              "modes": (1, 2, 3)},
    "3d": {"key_set": 0x1800363B0, "chgrp": 0x1800361F0,
           "vector_bytes": 0xC, "vectors": 3,
           "null_errors": {"secondary": 0x80000031, "third": 0x80000032,
                           "position": 0x80000033}},
    # FUN_180029e00 / 0x18002a490 pass null extension pointers for plain
    # KeyOn; point 3D wrappers pass a position pointer plus a 12-byte vector
    # copy, and line wrappers derive a four-float position first.
    "users": {
        "plain": {"handle": 0x18002A380, "id": 0x18002A650,
                  "handle_key_on": 0x18002A410, "id_key_on": 0x18002A6E0,
                  "chain": 0x180029E00, "id_chain": 0x18002A490,
                  "extended": False},
        "point": {"handle": 0x1800363B0, "handle_chgrp": 0x1800361F0,
                  "id": 0x180036900, "id_chgrp": 0x180036740,
                  "chain": 0x180029CC0, "id_chain": 0x180029EB0,
                  "position_floats": 3, "secondary_bytes": 0xC,
                  "extended": True},
        "line": {"handle": 0x1800365E0, "id": 0x180036A10,
                 "get_position": 0x180034E70, "position_floats": 4,
                 "extended": True},
    },
}


# BGM playback and fade. The Lua FadeOutBGM binding (0x140781ba0) converts
# 60 fps frames to milliseconds; stopStream treats "not playing" as success.
BGM_PLAYBACK = {
    "play": 0x1407D6940,
    "start": 0x140C52100,
    "stop": 0x140C52110,
    "fade_binding": 0x140781BA0,
    "fade": 0x1407D48C0,
    "frame_rate": 60,
    "manager_ids": {"current": 0x44C, "next": 0x450, "no_change": -1},
    "fade_out": {
        "export": 0x180016850, "fallback_stop": 0x1800161E0,
        "handle_table": 0x1800483D0, "handle_limit": 0x180048410,
        "invalid_handle": 0x8000000A, "not_playing": 0x8000000B,
        "already_fading": 0x80000000,
        "ms_per_tick": 5.333,
        "fields": {"state": 0x28C, "fader_flag": 0x293, "mode": 0x294,
                   "frames": 0x298, "step": 0x29C, "volume": 0x2A0,
                   "voice": 0x2A8, "channel": 0x148, "fader": 0x2C0},
        "playing": 3, "fading": 2, "stopped": 5,
    },
}


def fade_frames_to_ms(now_frame, max_frame):
    """FUN_140781ba0: integer frame delta at 60 fps, then milliseconds."""
    return int((int(max_frame) - int(now_frame)) / 60) * 1000


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


# nuSound2BankRegister (0x180299c0) -> 0x18002f370 -> 0x18002f1c0 takes the
# first free bank slot, then 0x18002eb80 parses the image in place. Slot state
# is at slot*0x804+0x42; cleanup 0x18002e7d0 reads the same records at
# 0x108+slot*0x2010 (the int-indexed base 0x46 in the setup function).
BANK_REGISTER = {
    "register": 0x180299C0, "find_slot": 0x18002F1C0,
    "setup": 0x18002EB80, "cleanup": 0x18002E7D0,
    "slots": 0x40, "slot_stride": 0x804,
    "slot_bank_ptr": 0x42, "slot_data_ptr": 0x44, "slot_voice_ids": 0x46,
    "record_base": 0x108, "record_stride": 0x2010,
    "record_voice_ids": 0x10,
    "stream_reserve": 0x80508, "stream_limit": 0x20000000,
    "version": (1, 2, 1),
    "header": {"tone_count": 0x0C, "data_offset": 0x10,
               "data_size": 0x14, "record_table": 0x18},
    "tone": {"length": 0x14, "data_offset": 0x18,
             "format_count": 0x1C, "wav_format": 0xBC},
}


def bank_setup_view(raw):
    """Fields read by FUN_18002eb80 from a shipped .nub bank image."""
    if len(raw) < 0x20:
        raise ValueError("short bank image")
    version = tuple(raw[:3])
    if version != BANK_REGISTER["version"]:
        raise ValueError("bank version %s" % (version,))
    header = BANK_REGISTER["header"]
    tone_count, data_offset, data_size, table = struct.unpack_from(
        "<4I", raw, header["tone_count"])
    tone = BANK_REGISTER["tone"]
    tones = []
    for index in range(tone_count):
        at = table + index * 4
        if at + 4 > len(raw):
            raise ValueError("tone table outside bank")
        record, = struct.unpack_from("<I", raw, at)
        if record + tone["wav_format"] + 8 > len(raw):
            raise ValueError("tone record outside bank")
        length, offset, formats = struct.unpack_from(
            "<3I", raw, record + tone["length"])
        tones.append({"length": length, "data_offset": offset,
                      "formats": formats})
    return {"version": version, "tone_count": tone_count,
            "data_offset": data_offset, "data_size": data_size,
            "record_table": table, "tones": tones}


def stream_reserve(total, size):
    """FUN_180035b80: running stream-byte total, -1 past the 0x20000000 cap."""
    if size < 0 or total + size > BANK_REGISTER["stream_limit"]:
        return -1
    return total + size


# FUN_180026a60 builds up to 32 chained voices. FUN_180025b80 fills one
# 0xd0-byte record per voice at instance +0x21c + index*0xd0 (0x180020370);
# FUN_180029220 applies it to the core voice after KeyOn.
CHAIN_VOICE_STATE = {
    "builder": 0x180025B80, "applier": 0x180029220,
    "slot": 0x21C, "stride": 0xD0, "count": 0x20, "floats": 0x34,
    "fields": {"volume": 0x00, "volume_db": 0x01, "pitch_cents": 0x02,
               "fx_volume": 0x03, "mix_volume": 0x04, "filter_a": 0x05,
               "filter_b": 0x06, "speaker_matrix": 0x07,
               "speaker_floats": 0x24, "reserved": 0x2B, "mode": 0x2C,
               "channel": 0x2D, "param_a": 0x2E, "param_b": 0x2F,
               "bus": 0x30, "bank": 0x31, "tone": 0x32, "voice": 0x33},
    "appliers": {"volume": 0x18001BF00, "fx_volume": 0x18001B1B0,
                 "pitch": 0x18001BE70, "filter_a": 0x18001B670,
                 "filter_b": 0x18001B520, "speaker": 0x18001BD30,
                 "bus": 0x18001B180, "mode": 0x18001C220},
    "voice_fields": {"volume": 0x2C, "fx_volume": 0x30, "pitch": 0x48,
                     "filter_a": 0x08, "filter_b": 0x44, "bus": 0x38,
                     "channel": 0x14, "core_voice": 0x08},
    "core_voice_table": {"lookup": 0x18001ED00, "offset": 0x44,
                         "stride": 0x178, "count": 0xC0},
    "modes": (1, 2, 7), "pitch_base": 2.0, "pitch_divisor": 1200.0,
    "db_scale": 20.0,
}


def clamp_unit(value):
    """FUN_18001bf00/b1b0/bd30: NaN or negative -> 0, above one -> 1."""
    if value != value or value < 0.0:
        return 0.0
    return 1.0 if value > 1.0 else value


def cents_to_pitch(cents):
    """FUN_18001be70: 2^(cents/1200), passed to bnusCoreVoiceSetPitch."""
    return CHAIN_VOICE_STATE["pitch_base"] ** \
        (cents / CHAIN_VOICE_STATE["pitch_divisor"])


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
        "extended_key_on": EXTENDED_KEY_ON,
        "bgm_playback": BGM_PLAYBACK,
        "playback": {
            "bgm_stream_handle": BGM_STREAM_HANDLE,
            "voice_slots": VOICE_SLOT_COUNT,
            "voice_stride": VOICE_RECORD_STRIDE,
            "voice_meta_base": VOICE_META_BASE,
            "voice_meta_stride": VOICE_META_STRIDE,
            "bank_set_errors": BANK_SET_ERRORS,
            "bank_setup": BANK_REGISTER,
            "chain_voice": CHAIN_VOICE_STATE,
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
