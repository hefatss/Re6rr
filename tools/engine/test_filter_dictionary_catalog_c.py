"""ctypes checks for the packed filter Lua line-shape inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import filter_dictionary_catalog as fdc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
FILE_BASE = 32
FILE_SIZE = 44
ROW_BASE = FILE_BASE + 17 * FILE_SIZE
ROW_SIZE = 24


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("row_count", U32), ("string_size", U32),
                ("source_bytes", U32), ("source_lines", U32)]


class File(ctypes.Structure):
    _fields_ = [("path_offset", U32), ("path_length", U32),
                ("source_size", U32), ("line_count", U32),
                ("active", U32), ("commented", U32), ("bool_count", U32),
                ("table", U32), ("function", U32),
                ("row_first", U32), ("row_count", U32)]


class Row(ctypes.Structure):
    _fields_ = [("file_index", U32), ("line_index", U32),
                ("byte_offset", U32), ("line_length", U32),
                ("kind", U32), ("value", U32)]


def configure(lib):
    lib.r6_filter_dictionary_parse.restype = ctypes.c_int
    lib.r6_filter_dictionary_parse.argtypes = [BUF, ctypes.c_size_t,
                                               ctypes.POINTER(Header)]
    lib.r6_filter_dictionary_file.restype = ctypes.c_int
    lib.r6_filter_dictionary_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                              ctypes.POINTER(File)]
    lib.r6_filter_dictionary_path.restype = ctypes.c_int
    lib.r6_filter_dictionary_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                              ctypes.c_size_t]
    lib.r6_filter_dictionary_row.restype = ctypes.c_int
    lib.r6_filter_dictionary_row.argtypes = [BUF, ctypes.c_size_t, U32,
                                             ctypes.POINTER(Row)]


def check(lib, files, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_filter_dictionary_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.row_count,
            header.source_bytes, header.source_lines) == (
        1, len(files), len(rows), fdc.EXPECTED_BYTES, fdc.EXPECTED_LINES)
    assert header.string_size == len(blob) - ROW_BASE - len(rows) * ROW_SIZE

    file = File()
    path = ctypes.create_string_buffer(96)
    expected = []
    for index, row in enumerate(files):
        name, size, lines, counts, local = row
        assert lib.r6_filter_dictionary_file(
            source, len(blob), index, ctypes.byref(file)) == R6_OK
        assert lib.r6_filter_dictionary_path(
            source, len(blob), index, path, len(path)) == R6_OK
        assert path.value.decode("ascii") == name
        assert (file.source_size, file.line_count, file.active,
                file.commented, file.bool_count, file.table,
                file.function, file.row_count, file.row_first) == (
            size, lines, counts[3], counts[4], counts[5], counts[0],
            counts[6], len(local), len(expected))
        expected.extend((index,) + item for item in local)
    row = Row()
    for index, item in enumerate(expected):
        assert lib.r6_filter_dictionary_row(
            source, len(blob), index, ctypes.byref(row)) == R6_OK
        assert (row.file_index, row.line_index, row.byte_offset,
                row.line_length, row.kind, row.value) == item
    print("Filter dictionaries: 17 files, 6493 classified rows and all "
          "byte spans match the dump")

    assert lib.r6_filter_dictionary_file(
        source, len(blob), len(files), ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_filter_dictionary_path(
        source, len(blob), len(files), path, len(path)) == R6_ERR_ARG
    assert lib.r6_filter_dictionary_row(
        source, len(blob), len(rows), ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_filter_dictionary_parse(
        source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_filter_dictionary_file(
        source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_filter_dictionary_row(
        source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_filter_dictionary_path(
        source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_filter_dictionary_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_filter_dictionary_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 16), (16, 6492), (20, 1),
                        (24, 156168), (28, 6617)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_filter_dictionary_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((4, 0), (8, 0), (12, 0), (32, 1), (40, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_filter_dictionary_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 17), (4, 6618), (12, 0xffffffff), (16, 7),
                        (20, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_filter_dictionary_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    print("Filter negatives: bad magic/header/file/row fields, truncation "
          "and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, rows = fdc.collect(args.dump)
    check(lib, files, rows, fdc.build(files, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
