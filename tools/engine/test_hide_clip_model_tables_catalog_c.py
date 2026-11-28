"""ctypes checks for the packed WANGAN hide-clip model-name tables."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import hide_clip_model_tables_catalog as hc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 36
FILE_SIZE = 36
SPAN_SIZE = 8
NAME_BASE = HEADER_SIZE + 6 * FILE_SIZE
STRING_BASE = NAME_BASE + 2972 * SPAN_SIZE
HEADER_FIELDS = ("version", "file_count", "name_count", "string_size",
                 "source_bytes", "line_count", "table_count")
FILE_FIELDS = ("path_offset", "path_length", "table_offset", "table_length",
               "timestamp_offset", "timestamp_length", "size", "lines",
               "names")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


def configure(lib):
    lib.r6_hide_clip_parse.restype = ctypes.c_int
    lib.r6_hide_clip_parse.argtypes = [BUF, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_hide_clip_file.restype = ctypes.c_int
    lib.r6_hide_clip_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                      ctypes.POINTER(File)]
    lib.r6_hide_clip_path.restype = ctypes.c_int
    lib.r6_hide_clip_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                      ctypes.c_size_t]
    lib.r6_hide_clip_table.restype = ctypes.c_int
    lib.r6_hide_clip_table.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                       ctypes.c_size_t]
    lib.r6_hide_clip_timestamp.restype = ctypes.c_int
    lib.r6_hide_clip_timestamp.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                           ctypes.c_size_t]
    lib.r6_hide_clip_name.restype = ctypes.c_int
    lib.r6_hide_clip_name.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                      ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_hide_clip_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 6, 2972, len(blob) - STRING_BASE, 140107, 2994, 3]

    file = File()
    text = ctypes.create_string_buffer(96)
    names = []
    for index, expected in enumerate(rows):
        assert lib.r6_hide_clip_file(source, len(blob), index,
                                     ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<9I", blob,
                                 HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.table_offset,
                       file.table_length, file.timestamp_offset,
                       file.timestamp_length, file.size, file.lines,
                       file.names)
        assert (file.size, file.lines, file.names) == \
            (expected[1], expected[2], len(expected[5]))
        assert lib.r6_hide_clip_path(source, len(blob), index,
                                     text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_hide_clip_table(source, len(blob), index,
                                      text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[4]
        assert lib.r6_hide_clip_timestamp(source, len(blob), index,
                                          text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[3]
        names.extend(expected[5])
    for index, expected in enumerate(names):
        assert lib.r6_hide_clip_name(source, len(blob), index,
                                     text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
        offset, length = struct.unpack_from("<2I", blob,
                                             NAME_BASE + index * SPAN_SIZE)
        assert blob[offset:offset + length].decode("ascii") == expected
    print("Hide-clip tables: 6 paths, tables, timestamps and 2972 names "
          "match the dump")

    assert lib.r6_hide_clip_file(source, len(blob), 6,
                                 ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_hide_clip_path(source, len(blob), 6,
                                 text, len(text)) == R6_ERR_ARG
    assert lib.r6_hide_clip_name(source, len(blob), 2972,
                                 text, len(text)) == R6_ERR_ARG
    assert lib.r6_hide_clip_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_hide_clip_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_hide_clip_name(source, len(blob), 0,
                                 text, 4) == R6_ERR_BUFFER
    assert lib.r6_hide_clip_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_hide_clip_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 5), (16, 2971), (20, 0), (24, 140106),
                        (28, 2993), (32, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_hide_clip_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((1, 3), (3, 12), (5, 18), (6, 0), (7, 2), (8, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_hide_clip_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot in (0, 2, 4):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, NAME_BASE + slot * 4, 0)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_hide_clip_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    offset, _ = struct.unpack_from("<2I", blob, NAME_BASE)
    bad = bytearray(blob)
    bad[offset] = ord(",")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_hide_clip_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    print("Hide-clip negatives: bad magic/header/file/name fields, "
          "out-of-range indexes, truncation and short buffers rejected")


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
