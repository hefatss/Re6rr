"""ctypes checks for the packed introductory-motion inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import introductory_motions_catalog as imc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 36
ROW_SIZE = 20
FUNCTION_BASE = HEADER_SIZE + 2 * ROW_SIZE
STRING_BASE = FUNCTION_BASE + 6 * 8
HEADER_FIELDS = ("version", "row_count", "name_count", "function_count",
                 "string_size", "start_frame", "blank_frame")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "left_offset", "left_length", "right_offset", "right_length", "wait")]


def configure(lib):
    lib.r6_introductory_parse.restype = ctypes.c_int
    lib.r6_introductory_parse.argtypes = [BUF, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_introductory_row.restype = ctypes.c_int
    lib.r6_introductory_row.argtypes = [BUF, ctypes.c_size_t, U32,
                                       ctypes.POINTER(Row)]
    lib.r6_introductory_name.restype = ctypes.c_int
    lib.r6_introductory_name.argtypes = [BUF, ctypes.c_size_t, U32, U32, BUF,
                                        ctypes.c_size_t]
    lib.r6_introductory_function.restype = ctypes.c_int
    lib.r6_introductory_function.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                             ctypes.c_size_t]


def check(lib, collection, blob):
    start, blank, rows, functions = collection
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_introductory_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 2, 4, 6, len(blob) - STRING_BASE, start, blank]

    row = Row()
    name = ctypes.create_string_buffer(32)
    for index, expected in enumerate(rows):
        assert lib.r6_introductory_row(source, len(blob), index,
                                       ctypes.byref(row)) == R6_OK
        assert struct.unpack_from("<5I", blob, HEADER_SIZE + index * ROW_SIZE) == (
            row.left_offset, row.left_length, row.right_offset,
            row.right_length, row.wait)
        assert row.wait == expected[2]
        for slot in (0, 1):
            assert lib.r6_introductory_name(source, len(blob), index, slot,
                                            name, len(name)) == R6_OK
            assert name.value.decode("ascii") == expected[slot]

    function = ctypes.create_string_buffer(64)
    for index, expected in enumerate(functions):
        assert lib.r6_introductory_function(source, len(blob), index,
                                            function, len(function)) == R6_OK
        assert function.value.decode("ascii") == expected
    print("Introductory motions: 2 rows, 4 .MED names, waits 20/60 and 6 "
          "accessor names match the dump")

    assert lib.r6_introductory_row(source, len(blob), 2,
                                   ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_introductory_name(source, len(blob), 0, 2,
                                    name, len(name)) == R6_ERR_ARG
    assert lib.r6_introductory_function(source, len(blob), 6,
                                        function, len(function)) == R6_ERR_ARG
    assert lib.r6_introductory_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_introductory_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_introductory_name(source, len(blob), 0, 0,
                                    name, 4) == R6_ERR_BUFFER
    assert lib.r6_introductory_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_introductory_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1), (16, 3), (20, 5), (24, 1),
                        (28, 1), (32, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_introductory_parse(source, len(bad),
                                         ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((1, 0), (2, 0), (3, 0), (4, 19)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_introductory_parse(source, len(bad),
                                         ctypes.byref(header)) == R6_ERR_FORMAT
    print("Introductory-motion negatives: bad magic/header/row fields, "
          "out-of-range slots, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    collection = imc.collect(args.dump)
    check(lib, collection, imc.build(collection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
