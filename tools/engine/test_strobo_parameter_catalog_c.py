"""ctypes checks for the packed Strobo parameter inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import strobo_parameter_catalog as slo  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 36
FILE_SIZE = 32
TABLE_SIZE = 16
ROW_SIZE = 8
STRING_BASE = 196
HEADER_FIELDS = ("version", "file_count", "table_count", "row_count",
                 "function_count", "string_size", "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines", "debug",
               "table_base", "row_base", "function_base")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Table(ctypes.Structure):
    _fields_ = [("name_offset", U32), ("name_length", U32),
                ("row_base", U32), ("rows", U32)]


class Row(ctypes.Structure):
    _fields_ = [("first", U32), ("second", U32)]


def configure(lib):
    for name, args in (
        ("r6_strobo_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_strobo_file", [BUF, ctypes.c_size_t, ctypes.POINTER(File)]),
        ("r6_strobo_path", [BUF, ctypes.c_size_t, BUF, ctypes.c_size_t]),
        ("r6_strobo_table", [BUF, ctypes.c_size_t, U32,
                             ctypes.POINTER(Table)]),
        ("r6_strobo_table_name", [BUF, ctypes.c_size_t, U32, BUF,
                                  ctypes.c_size_t]),
        ("r6_strobo_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_strobo_function", [BUF, ctypes.c_size_t, U32, BUF,
                                ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_strobo_parse(source, len(blob),
                               ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 2, 8, 4, len(blob) - STRING_BASE, 3771]

    file = File()
    text = ctypes.create_string_buffer(96)
    assert lib.r6_strobo_file(source, len(blob),
                              ctypes.byref(file)) == R6_OK
    assert struct.unpack_from("<8I", blob, HEADER_SIZE) == \
        tuple(getattr(file, name) for name in FILE_FIELDS)
    assert (file.size, file.lines, file.debug) == (3771, 95, 0)
    assert lib.r6_strobo_path(source, len(blob),
                              text, len(text)) == R6_OK
    assert text.value.decode("ascii") == entry[0]

    table = Table()
    for index, expected in enumerate(entry[4]):
        assert lib.r6_strobo_table(source, len(blob), index,
                                   ctypes.byref(table)) == R6_OK
        assert struct.unpack_from("<4I", blob,
                                  68 + index * TABLE_SIZE) == \
            (table.name_offset, table.name_length, table.row_base,
             table.rows)
        assert (table.rows, table.row_base) == \
            ((5, 0) if index == 0 else (3, 5))
        assert lib.r6_strobo_table_name(source, len(blob), index,
                                        text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    rows = [row for _, pairs in entry[4] for row in pairs]
    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_strobo_row(source, len(blob), index,
                                 ctypes.byref(row)) == R6_OK
        assert (row.first, row.second) == expected
    for index, expected in enumerate(entry[5]):
        assert lib.r6_strobo_function(source, len(blob), index,
                                      text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
    print("Strobo: 1 file, 2 tables, 8 integer pairs and 4 functions match")

    assert lib.r6_strobo_table(source, len(blob), 2,
                               ctypes.byref(table)) == R6_ERR_ARG
    assert lib.r6_strobo_row(source, len(blob), 8,
                             ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_strobo_function(source, len(blob), 4,
                                  text, len(text)) == R6_ERR_ARG
    assert lib.r6_strobo_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_strobo_file(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_strobo_path(source, len(blob), text, 4) == R6_ERR_BUFFER
    assert lib.r6_strobo_parse(source, len(blob) - 1,
                               ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_strobo_parse(source, len(bad),
                               ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 0), (16, 1), (20, 7), (24, 3),
                        (28, 0), (32, 3770)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_strobo_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 0), (3, 94), (4, 1), (6, 7)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_strobo_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 5), (3, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, 68 + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_strobo_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 61), (1, 61)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, 100 + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_strobo_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    print("Strobo negatives: bad magic/header/file/table/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = slo.collect(args.dump)
    check(lib, entry, slo.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
