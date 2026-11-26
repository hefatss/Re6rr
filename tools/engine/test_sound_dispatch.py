"""Check the sys::Sound::Impl dispatch array readers against shipped facts."""

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


class BankSlot(ctypes.Structure):
    _fields_ = [("handle", ctypes.c_uint32), ("state", ctypes.c_uint32),
                ("ready", ctypes.c_int)]


class LoopRecord(ctypes.Structure):
    _fields_ = [("flag", ctypes.c_uint32), ("tone", ctypes.c_uint32)]


class Positional(ctypes.Structure):
    _fields_ = [("bank", ctypes.c_uint32), ("tone", ctypes.c_int32),
                ("frames", ctypes.c_int32), ("x", ctypes.c_float),
                ("y", ctypes.c_float), ("z", ctypes.c_float)]


def check(dump):
    dispatch = audio_events.dispatch_facts(dump)
    bank = dispatch["bank_table"]
    requests = dispatch["requests"]
    assert bank == {"stride": 0x20, "handle": 0x18, "state": 0x1C,
                    "ready": 3}
    assert requests["count"] == 0x22 and requests["loop_slot"] == 0x21
    assert requests["loop_stride"] == 8 and requests["positional_stride"] == 0x24

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_sound_bank_slot.restype = ctypes.c_int
    lib.r6_sound_bank_slot.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32,
                                       ctypes.POINTER(BankSlot)]
    lib.r6_sound_loop_record.restype = ctypes.c_int
    lib.r6_sound_loop_record.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_uint32,
                                         ctypes.POINTER(LoopRecord)]
    lib.r6_sound_positional_record.restype = ctypes.c_int
    lib.r6_sound_positional_record.argtypes = [ctypes.c_void_p,
                                               ctypes.c_size_t,
                                               ctypes.c_uint32,
                                               ctypes.POINTER(Positional)]

    banks = bytearray(8 * bank["stride"])
    for index in range(8):
        struct.pack_into("<I", banks, index * 0x20 + 0x18,
                         0x1800A000 + index * 0x40)
        struct.pack_into("<I", banks, index * 0x20 + 0x1C,
                         3 if index % 2 == 0 else 0)
    source = ctypes.create_string_buffer(bytes(banks), len(banks))
    slot = BankSlot()
    for index in range(8):
        assert lib.r6_sound_bank_slot(source, len(banks), index,
                                      ctypes.byref(slot)) == R6_OK
        assert slot.handle == 0x1800A000 + index * 0x40
        assert slot.state == (3 if index % 2 == 0 else 0)
        assert slot.ready == (1 if index % 2 == 0 else 0)
    assert lib.r6_sound_bank_slot(source, len(banks), 8,
                                  ctypes.byref(slot)) == R6_ERR_ARG
    assert lib.r6_sound_bank_slot(source, len(banks) - 1, 7,
                                  ctypes.byref(slot)) == R6_ERR_ARG
    assert lib.r6_sound_bank_slot(source, len(banks), 0, None) == R6_ERR_ARG
    assert lib.r6_sound_bank_slot(None, len(banks), 0,
                                  ctypes.byref(slot)) == R6_ERR_ARG

    loops = bytearray(requests["count"] * requests["loop_stride"])
    for index in range(requests["count"]):
        struct.pack_into("<II", loops, index * 8, index & 1, index + 0x40)
    source = ctypes.create_string_buffer(bytes(loops), len(loops))
    record = LoopRecord()
    for index in range(requests["count"]):
        assert lib.r6_sound_loop_record(source, len(loops), index,
                                        ctypes.byref(record)) == R6_OK
        assert (record.flag, record.tone) == (index & 1, index + 0x40)
    scene = requests["loop_slot"]
    assert lib.r6_sound_loop_record(source, len(loops), scene,
                                    ctypes.byref(record)) == R6_OK
    assert record.tone == scene + 0x40
    assert lib.r6_sound_loop_record(source, len(loops), requests["count"],
                                    ctypes.byref(record)) == R6_ERR_ARG

    positional = bytearray(2 * requests["positional_stride"])
    struct.pack_into("<Iiifff", positional, 0, 2, -1, 30, 1.5, -2.0, 3.25)
    struct.pack_into("<Iiifff", positional, 0x24, 5, 47, 0, -1.0, 0.0, 0.5)
    source = ctypes.create_string_buffer(bytes(positional), len(positional))
    row = Positional()
    assert lib.r6_sound_positional_record(source, len(positional), 0,
                                          ctypes.byref(row)) == R6_OK
    assert (row.bank, row.tone, row.frames) == (2, -1, 30)
    assert (row.x, row.y, row.z) == (1.5, -2.0, 3.25)
    assert lib.r6_sound_positional_record(source, len(positional), 1,
                                          ctypes.byref(row)) == R6_OK
    assert (row.bank, row.tone, row.frames) == (5, 47, 0)
    assert (row.x, row.y, row.z) == (-1.0, 0.0, 0.5)
    assert lib.r6_sound_positional_record(source, len(positional), 2,
                                          ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_sound_positional_record(source, len(positional) - 1, 1,
                                          ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_sound_positional_record(source, len(positional), 0,
                                          None) == R6_ERR_ARG
    print("sound dispatch: 8 bank slots, 34 loop records and 2 positional "
          "0x24 records match the shipped ABI; out-of-range and short input "
          "rejected")


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
