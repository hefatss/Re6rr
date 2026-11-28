"""ctypes checks for the packed custom-frame inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import custom_frame_catalog as cfc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
ROW_SIZE = 36
FUNCTION_BASE = HEADER_SIZE + 183 * ROW_SIZE
STRING_BASE = FUNCTION_BASE + 6 * 8
HEADER_FIELDS = ("version", "row_count", "name_count", "function_count",
                 "string_size", "source_size")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [("id", U32), ("name_offset", U32 * 4),
                ("name_length", U32 * 4)]


def configure(lib):
    lib.r6_custom_frame_parse.restype = ctypes.c_int
    lib.r6_custom_frame_parse.argtypes = [BUF, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_custom_frame_row.restype = ctypes.c_int
    lib.r6_custom_frame_row.argtypes = [BUF, ctypes.c_size_t, U32,
                                       ctypes.POINTER(Row)]
    lib.r6_custom_frame_texture.restype = ctypes.c_int
    lib.r6_custom_frame_texture.argtypes = [BUF, ctypes.c_size_t, U32, U32,
                                            BUF, ctypes.c_size_t]
    lib.r6_custom_frame_function.restype = ctypes.c_int
    lib.r6_custom_frame_function.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                             ctypes.c_size_t]


def check(lib, collection, blob):
    rows, functions = collection
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_custom_frame_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 183, 732, 6, len(blob) - STRING_BASE, 26386]

    row = Row()
    name = ctypes.create_string_buffer(32)
    for index, (item, names) in enumerate(rows):
        assert lib.r6_custom_frame_row(source, len(blob), index,
                                       ctypes.byref(row)) == R6_OK
        raw = struct.unpack_from("<9I", blob, HEADER_SIZE + index * ROW_SIZE)
        assert raw == (row.id,) + tuple(row.name_offset) + \
            tuple(row.name_length)
        assert row.id == item
        for slot, expected in enumerate(names):
            assert lib.r6_custom_frame_texture(source, len(blob), index, slot,
                                               name, len(name)) == R6_OK
            assert name.value.decode("ascii") == expected
            assert len(expected) == 21

    function = ctypes.create_string_buffer(64)
    for index, expected in enumerate(functions):
        assert lib.r6_custom_frame_function(source, len(blob), index,
                                            function, len(function)) == R6_OK
        assert function.value.decode("ascii") == expected
    print("Custom frames: 183 rows, 732 texture names and 6 accessor names "
          "match the dump")

    assert lib.r6_custom_frame_row(source, len(blob), 183,
                                   ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_custom_frame_texture(source, len(blob), 0, 4,
                                       name, len(name)) == R6_ERR_ARG
    assert lib.r6_custom_frame_function(source, len(blob), 6,
                                        function, len(function)) == R6_ERR_ARG
    assert lib.r6_custom_frame_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_custom_frame_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_custom_frame_texture(source, len(blob), 0, 0,
                                       None, 32) == R6_ERR_ARG
    assert lib.r6_custom_frame_texture(source, len(blob), 0, 0,
                                       name, 4) == R6_ERR_BUFFER
    assert lib.r6_custom_frame_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_custom_frame_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 182), (16, 731), (20, 5), (24, 1),
                        (28, 26385)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_custom_frame_parse(source, len(bad),
                                         ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 2), (1, 22), (2, 0), (2, 20)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_custom_frame_parse(source, len(bad),
                                         ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[struct.unpack_from("<I", blob, HEADER_SIZE + 4)[0]] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_custom_frame_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    print("Custom-frame negatives: bad magic/header/row/name fields, out-of-"
          "range slots, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    collection = cfc.collect(args.dump)
    check(lib, collection, cfc.build(collection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
