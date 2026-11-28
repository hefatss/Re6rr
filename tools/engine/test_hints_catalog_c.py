"""ctypes checks for the packed hints.dat record inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import hints_catalog as hc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
ROW_SIZE = 16
FIELDS = ("version", "record_count", "stride", "source_size", "distinct")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


class Row(ctypes.Structure):
    _fields_ = [("words", U32 * 4)]


def configure(lib):
    lib.r6_hints_parse.restype = ctypes.c_int
    lib.r6_hints_parse.argtypes = [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_hints_row.restype = ctypes.c_int
    lib.r6_hints_row.argtypes = [BUF, ctypes.c_size_t, U32,
                                ctypes.POINTER(Row)]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_hints_parse(source, len(blob),
                              ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in FIELDS] == [
        1, 67, 16, 1072, 61]

    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_hints_row(source, len(blob), index,
                                ctypes.byref(row)) == R6_OK
        assert list(row.words) == list(expected)
        assert struct.unpack_from("<4I", blob,
                                  HEADER_SIZE + index * ROW_SIZE) == expected
    print("Hints: 67 stride-16 records and 61 distinct words match hints.dat")

    assert lib.r6_hints_row(source, len(blob), 67,
                            ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_hints_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_hints_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_hints_parse(source, len(blob) - 1,
                              ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_hints_parse(source, len(bad),
                              ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 66), (16, 15), (20, 1071), (24, 60)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_hints_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[HEADER_SIZE + 15] = 1
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_hints_parse(source, len(bad),
                              ctypes.byref(header)) == R6_ERR_FORMAT
    print("Hints negatives: bad magic/header/row fields, truncation and null "
          "outputs rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = hc.collect(args.dump)
    check(lib, rows, hc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
