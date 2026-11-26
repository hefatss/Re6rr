"""Check the 32 chained-voice 0xd0 state records in C."""

import ctypes
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1

COUNT = 0x20
STRIDE = 0xD0
FLOATS = 0x34


class ChainState(ctypes.Structure):
    _fields_ = [("values", ctypes.c_float * FLOATS)]


POW_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                          ctypes.c_double, ctypes.c_double)
EXP2_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                           ctypes.c_double)


class Math(ctypes.Structure):
    _fields_ = [("user", ctypes.c_void_p), ("pow_value", POW_FN),
                ("exp2_value", EXP2_FN)]


def configure(lib):
    lib.r6_voice_chain_read.restype = ctypes.c_int
    lib.r6_voice_chain_read.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32,
                                       ctypes.POINTER(ChainState)]
    lib.r6_voice_chain_write.restype = ctypes.c_int
    lib.r6_voice_chain_write.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_uint32,
                                        ctypes.POINTER(ChainState)]
    lib.r6_voice_chain_apply.restype = ctypes.c_int
    lib.r6_voice_chain_apply.argtypes = [ctypes.POINTER(ChainState),
                                         ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(Math)]


def check(dump):
    facts = audio_events.CHAIN_VOICE_STATE
    assert (facts["count"], facts["stride"], facts["floats"]) == \
        (COUNT, STRIDE, FLOATS)
    assert facts["fields"] == {
        "volume": 0x00, "volume_db": 0x01, "pitch_cents": 0x02,
        "fx_volume": 0x03, "mix_volume": 0x04, "filter_a": 0x05,
        "filter_b": 0x06, "speaker_matrix": 0x07,
        "speaker_floats": 0x24, "reserved": 0x2B, "mode": 0x2C,
        "channel": 0x2D, "param_a": 0x2E, "param_b": 0x2F,
        "bus": 0x30, "bank": 0x31, "tone": 0x32, "voice": 0x33}

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    raw = bytearray(COUNT * STRIDE)
    for index in range(COUNT):
        values = [float(index * FLOATS + slot) * 0.125 - 3.0
                  for slot in range(FLOATS)]
        struct.pack_into("<%df" % FLOATS, raw, index * STRIDE, *values)
    source = ctypes.create_string_buffer(bytes(raw), len(raw))
    state = ChainState()
    for index in range(COUNT):
        want = struct.unpack_from("<%df" % FLOATS, raw, index * STRIDE)
        assert lib.r6_voice_chain_read(source, len(raw), index,
                                       ctypes.byref(state)) == R6_OK
        assert list(state.values) == list(want), index

    for index in range(COUNT):
        values = [float(index + slot) * -0.0625 + 1.0
                  for slot in range(FLOATS)]
        state.values = (ctypes.c_float * FLOATS)(*values)
        assert lib.r6_voice_chain_write(source, len(raw), index,
                                        ctypes.byref(state)) == R6_OK
        struct.pack_into("<%df" % FLOATS, raw, index * STRIDE, *values)
    assert source.raw == bytes(raw)

    assert lib.r6_voice_chain_read(source, len(raw), COUNT,
                                   ctypes.byref(state)) == R6_ERR_ARG
    assert lib.r6_voice_chain_read(source, len(raw) - 1, 0,
                                   ctypes.byref(state)) == R6_ERR_ARG
    assert lib.r6_voice_chain_read(source, len(raw), 0, None) == R6_ERR_ARG
    assert lib.r6_voice_chain_write(source, len(raw), 0, None) == R6_ERR_ARG
    assert lib.r6_voice_chain_read(None, len(raw), 0,
                                   ctypes.byref(state)) == R6_ERR_ARG

    fields = facts["fields"]
    voice_offsets = facts["voice_fields"]
    values = [0.0] * FLOATS
    values[fields["volume"]] = float("nan")
    values[fields["fx_volume"]] = 2.0
    values[fields["pitch_cents"]] = 1200.0
    values[fields["filter_a"]] = -0.5
    values[fields["filter_b"]] = 0.25
    values[fields["bus"]] = 6.0
    values[fields["channel"]] = 21.0
    state.values = (ctypes.c_float * FLOATS)(*values)
    voice = ctypes.create_string_buffer(b"\xcc" * 0x4C, 0x4C)
    pow_cb = POW_FN(lambda user, base, exponent: math.pow(base, exponent))
    exp2_cb = EXP2_FN(lambda user, exponent: math.pow(2.0, exponent))
    sink = Math(None, pow_cb, exp2_cb)
    assert lib.r6_voice_chain_apply(ctypes.byref(state), voice, len(voice),
                                    ctypes.byref(sink)) == R6_OK
    expected = {
        voice_offsets["volume"]: struct.pack(
            "<f", audio_events.clamp_unit(float("nan"))),
        voice_offsets["fx_volume"]: struct.pack("<f", 1.0),
        voice_offsets["pitch"]: struct.pack(
            "<f", audio_events.cents_to_pitch(1200.0)),
        voice_offsets["filter_a"]: struct.pack("<f", 0.0),
        voice_offsets["filter_b"]: struct.pack("<f", 0.25),
        voice_offsets["bus"]: struct.pack("<I", 6),
        voice_offsets["channel"]: struct.pack("<I", 21),
    }
    for offset, blob in expected.items():
        assert voice.raw[offset:offset + len(blob)] == blob, offset
    for offset in range(len(voice.raw)):
        if not any(offset in range(at, at + len(blob))
                   for at, blob in expected.items()):
            assert voice.raw[offset] == 0xCC, offset

    assert lib.r6_voice_chain_apply(ctypes.byref(state), voice, 0x4B,
                                    ctypes.byref(sink)) == R6_ERR_ARG
    assert lib.r6_voice_chain_apply(None, voice, len(voice),
                                    ctypes.byref(sink)) == R6_ERR_ARG
    assert lib.r6_voice_chain_apply(ctypes.byref(state), None, len(voice),
                                    ctypes.byref(sink)) == R6_ERR_ARG
    assert lib.r6_voice_chain_apply(ctypes.byref(state), voice, len(voice),
                                    None) == R6_ERR_ARG
    assert lib.r6_voice_chain_apply(ctypes.byref(state), voice, len(voice),
                                    ctypes.byref(Math())) == R6_ERR_ARG
    print("voice chain: %d records x %d f32 slots read and write exact bytes, "
          "and 7 core fields applied with native clamp/pitch; bad index, "
          "short buffer and null arguments rejected" % (COUNT, FLOATS))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
