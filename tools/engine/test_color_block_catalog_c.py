"""ctypes checks for the packed MA61 color block inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import color_block_catalog as clr  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 52
FILE_SIZE = 24
ROW_SIZE = 16
ROW_BASE = HEADER_SIZE + 2 * FILE_SIZE
STRING_BASE = ROW_BASE + 45 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "line_count",
                 "string_size", "source_bytes", "token_count", "vec4_max",
                 "float_max", "int_max", "reserved")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines", "first_line",
               "row_base")
ROW_FIELDS = ("name_offset", "name_length", "line", "token_offset")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in ROW_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_color_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_color_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_color_path", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_color_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_color_name", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_color_token", [BUF, ctypes.c_size_t, U32, U32, BUF,
                            ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_color_parse(source, len(blob),
                              ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 2, 45, 1194, len(blob) - STRING_BASE, 40196, 19, 3, 4, 3, 0]
    text = ctypes.create_string_buffer(96)
    file = File()
    for index, expected in enumerate(files):
        assert lib.r6_color_file(source, len(blob), index,
                                 ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<6I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == tuple(getattr(file, name) for name in FILE_FIELDS)
        row_base = sum(len(prior[4]) for prior in files[:index])
        assert (file.size, file.lines, file.first_line, file.row_base) == \
            (expected[1], expected[2], expected[3], row_base)
        assert lib.r6_color_path(source, len(blob), index,
                                 text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    row = Row()
    for file_index, entry in enumerate(files):
        row_base = sum(len(prior[4]) for prior in files[:file_index])
        for local, (name, line, tokens) in enumerate(entry[4]):
            index = row_base + local
            assert lib.r6_color_row(source, len(blob), index,
                                    ctypes.byref(row)) == R6_OK
            raw = struct.unpack_from("<4I", blob, ROW_BASE + index * ROW_SIZE)
            assert raw == tuple(getattr(row, name_field)
                                for name_field in ROW_FIELDS)
            assert row.line == line
            assert lib.r6_color_name(source, len(blob), index,
                                     text, len(text)) == R6_OK
            assert text.value.decode("ascii") == name
            for slot, token in enumerate(tokens):
                assert lib.r6_color_token(source, len(blob), index, slot,
                                          text, len(text)) == R6_OK
                assert text.value.decode("ascii") == token.decode("ascii")
    print("MA61 colors: 2 files, 45 blocks and 855 tokens match")

    assert lib.r6_color_file(source, len(blob), 2, ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_color_path(source, len(blob), 2, text, len(text)) == R6_ERR_ARG
    assert lib.r6_color_row(source, len(blob), 45, ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_color_token(source, len(blob), 0, 19,
                              text, len(text)) == R6_ERR_ARG
    assert lib.r6_color_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_color_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_color_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_color_path(source, len(blob), 0, text, 4) == R6_ERR_BUFFER
    assert lib.r6_color_token(source, len(blob), 0, 0,
                              text, 2) == R6_ERR_BUFFER
    assert lib.r6_color_parse(source, len(blob) - 1,
                              ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_color_parse(source, len(bad),
                              ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1), (16, 44), (20, 1193), (24, 0),
                        (28, 40195), (32, 18), (36, 2), (40, 3), (44, 2),
                        (48, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_color_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 8064), (3, 246), (4, 28), (5, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_color_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (2, 30), (3, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_color_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    print("MA61 color negatives: bad magic/header/file/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = clr.collect(args.dump)
    check(lib, files, clr.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
