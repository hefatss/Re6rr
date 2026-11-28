"""ctypes checks for the packed vinyl selector inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import vinyl_select_catalog as vsl  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 44
FILE_SIZE = 16
ROW_SIZE = 12
FILE_BASE = HEADER_SIZE
ROW_BASE = FILE_BASE + 149 * FILE_SIZE
STRING_BASE = ROW_BASE + 7450 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "source_bytes",
                 "line_count", "id_min", "id_max", "string_size", "reserved")
FILE_FIELDS = ("name_offset", "name_length", "size", "row_base")
ROW_FIELDS = ("line", "ident", "value_offset")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in ROW_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_vsl_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_vsl_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_vsl_name", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_vsl_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_vsl_value", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_vsl_parse(source, len(blob),
                            ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 149, 7450, 722358, 93, 59, 108, len(blob) - STRING_BASE, 0]
    text = ctypes.create_string_buffer(96)
    file = File()
    for index, expected in enumerate(files):
        assert lib.r6_vsl_file(source, len(blob), index,
                               ctypes.byref(file)) == R6_OK
        packed = struct.unpack_from("<4I", blob, FILE_BASE + index * FILE_SIZE)
        assert packed == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.row_base) == (expected[1], index * 50)
        assert lib.r6_vsl_name(source, len(blob), index,
                               text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_vsl_row(source, len(blob), index,
                              ctypes.byref(row)) == R6_OK
        packed = struct.unpack_from("<3I", blob, ROW_BASE + index * ROW_SIZE)
        assert packed == tuple(getattr(row, name) for name in ROW_FIELDS)
        assert (row.line, row.ident) == (expected[0], expected[1])
        assert lib.r6_vsl_value(source, len(blob), index,
                                text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[2].decode("ascii")
    print("Vinyl selectors: 149 files, 7450 rows and 50 ids match")

    assert lib.r6_vsl_file(source, len(blob), 149, ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_vsl_row(source, len(blob), 7450, ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_vsl_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_vsl_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_vsl_name(source, len(blob), 0, text, 4) == R6_ERR_BUFFER
    assert lib.r6_vsl_value(source, len(blob), 0, text, 1) == R6_ERR_BUFFER
    assert lib.r6_vsl_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_vsl_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 148), (16, 7449), (20, 722357),
                        (24, 92), (28, 58), (32, 107), (36, 0), (40, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_vsl_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 722357), (3, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_vsl_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 58), (2, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_vsl_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    print("Vinyl selector negatives: bad magic/header/file/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, rows = vsl.collect(args.dump)
    check(lib, files, rows, vsl.build(files, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
