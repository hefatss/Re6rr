"""Check the nuSound2 bank slot scan against the shipped ABI."""

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
R6_ERR_NOT_FOUND = -7
COUNT = 0x40
STRIDE = 0x804
POINTER = 0x42


def check(dump):
    setup = audio_events.BANK_REGISTER
    assert (setup["slots"], setup["slot_stride"]) == (COUNT, STRIDE)
    assert audio_events.BANK_SET_ERRORS["no_slot"] == 0x8000001B

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_bank_slot_find.restype = ctypes.c_int
    lib.r6_bank_slot_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_uint32)]
    index = ctypes.c_uint32(0xFFFFFFFF)
    raw = bytearray(COUNT * STRIDE)
    source = ctypes.create_string_buffer(bytes(raw), len(raw))
    assert lib.r6_bank_slot_find(source, len(raw),
                                 ctypes.byref(index)) == R6_OK
    assert index.value == 0

    for used in range(1, COUNT + 1):
        struct.pack_into("<Q", raw, (used - 1) * STRIDE + POINTER,
                         0x18000000 + used)
        source = ctypes.create_string_buffer(bytes(raw), len(raw))
        result = lib.r6_bank_slot_find(source, len(raw), ctypes.byref(index))
        if used < COUNT:
            assert result == R6_OK and index.value == used
        else:
            assert result == R6_ERR_NOT_FOUND
    short = ctypes.create_string_buffer(bytes(raw[:-1]), len(raw) - 1)
    assert lib.r6_bank_slot_find(short, len(raw) - 1,
                                 ctypes.byref(index)) == R6_ERR_ARG
    assert lib.r6_bank_slot_find(source, len(raw), None) == R6_ERR_ARG
    assert lib.r6_bank_slot_find(None, len(raw),
                                 ctypes.byref(index)) == R6_ERR_ARG
    print("bank slots: first free slot found across all %d slots at stride "
          "0x804; full table, short buffer and null arguments rejected" % COUNT)


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
