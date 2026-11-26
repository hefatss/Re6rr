"""Check the 32 chained-voice 0xd0 state records in C."""

import ctypes
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


def configure(lib):
    lib.r6_voice_chain_read.restype = ctypes.c_int
    lib.r6_voice_chain_read.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32,
                                       ctypes.POINTER(ChainState)]
    lib.r6_voice_chain_write.restype = ctypes.c_int
    lib.r6_voice_chain_write.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_uint32,
                                        ctypes.POINTER(ChainState)]


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
    print("voice chain: %d records x %d f32 slots read and write exact bytes; "
          "bad index, short buffer and null arguments rejected" %
          (COUNT, FLOATS))


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
