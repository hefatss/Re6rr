"""ctypes checks for the packed Zenichi name-plate inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import zenichi_config_catalog as zcc  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 24
ROW_BASE = HEADER_SIZE
ROW_SIZE = 20
FIELDS = ["item", "variation", "name_offset", "name_length", "layout"]


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "version", "row_count", "string_size", "source_size")]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_zenichi_parse.restype = ctypes.c_int
    lib.r6_zenichi_parse.argtypes = [BUF, ctypes.c_size_t,
                                     ctypes.POINTER(Header)]
    lib.r6_zenichi_row.restype = ctypes.c_int
    lib.r6_zenichi_row.argtypes = [BUF, ctypes.c_size_t, U32,
                                   ctypes.POINTER(Row)]
    lib.r6_zenichi_find_id.restype = ctypes.c_int
    lib.r6_zenichi_find_id.argtypes = [BUF, ctypes.c_size_t, U32,
                                       ctypes.POINTER(Row)]
    lib.r6_zenichi_name.restype = ctypes.c_int
    lib.r6_zenichi_name.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                    ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_zenichi_parse(source, len(blob),
                                ctypes.byref(header)) == R6_OK
    assert (header.version, header.row_count, header.source_size) == (
        1, len(rows), zcc.SOURCE_SIZE)
    assert header.string_size == len(blob) - HEADER_SIZE - len(rows) * ROW_SIZE

    row = Row()
    name = ctypes.create_string_buffer(64)
    for index, expected in enumerate(rows):
        fields = struct.unpack_from("<5I", blob, ROW_BASE + index * ROW_SIZE)
        assert lib.r6_zenichi_row(source, len(blob), index,
                                  ctypes.byref(row)) == R6_OK
        assert [getattr(row, field) for field in FIELDS] == list(fields)
        assert (fields[0], fields[1], fields[4]) == (
            expected[0], expected[1], expected[3])
        assert lib.r6_zenichi_find_id(source, len(blob), expected[0],
                                      ctypes.byref(row)) == R6_OK
        assert row.item == expected[0]
        assert lib.r6_zenichi_name(source, len(blob), index, name,
                                   len(name)) == R6_OK
        assert name.value.decode("ascii") == expected[2]
    print("Zenichi: 276 name-plate rows, ids, variations, layouts and "
          "texture names match the dump")

    assert lib.r6_zenichi_find_id(source, len(blob), 277,
                                  ctypes.byref(row)) == R6_ERR_NOT_FOUND
    assert lib.r6_zenichi_row(source, len(blob), len(rows),
                              ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_zenichi_name(source, len(blob), len(rows),
                               name, len(name)) == R6_ERR_ARG
    assert lib.r6_zenichi_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_zenichi_find_id(source, len(blob), 1, None) == R6_ERR_ARG
    assert lib.r6_zenichi_name(source, len(blob), 0, name, 4) == R6_ERR_BUFFER
    assert lib.r6_zenichi_parse(source, len(blob) - 1,
                                ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_zenichi_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 275), (16, 1), (20, 30208)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_zenichi_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    for index, value in ((0, 2), (1, 0), (1, 7), (4, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + index * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_zenichi_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_OK
        assert lib.r6_zenichi_row(source, len(bad), 0,
                                  ctypes.byref(row)) == R6_ERR_FORMAT
    print("Zenichi negatives: bad magic/header/row fields, absent id, "
          "truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = zcc.collect(args.dump)
    check(lib, rows, zcc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
