"""ctypes checks for the packed NeonColor row inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import neon_color_catalog as neo  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 48
ROW_SIZE = 32
STRING_BASE = HEADER_SIZE + 6 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "line_count",
                 "string_size", "source_bytes", "comment_rows", "reserved",
                 "path_offset", "path_length")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [("token_offset", U32 * 3), ("token_length", U32 * 3),
                ("has_comment", U32), ("line", U32)]


def configure(lib):
    for name, args in (
        ("r6_neon_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_neon_path", [BUF, ctypes.c_size_t, BUF, ctypes.c_size_t]),
        ("r6_neon_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_neon_token", [BUF, ctypes.c_size_t, U32, U32, BUF,
                           ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    path, size, lines, rows = entry
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_neon_parse(source, len(blob), ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 6, 31, len(blob) - STRING_BASE, 1180, 6, 0,
        struct.unpack_from("<2I", blob, 40)[0],
        struct.unpack_from("<2I", blob, 40)[1]]
    text = ctypes.create_string_buffer(96)
    assert lib.r6_neon_path(source, len(blob), text, len(text)) == R6_OK
    assert text.value.decode("ascii") == path
    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_neon_row(source, len(blob), index,
                               ctypes.byref(row)) == R6_OK
        raw = struct.unpack_from("<8I", blob, HEADER_SIZE + index * ROW_SIZE)
        assert raw == tuple(list(row.token_offset) + list(row.token_length) +
                            [row.has_comment, row.line])
        assert row.has_comment == 1 and row.line == 9 + index
        for slot, value in enumerate(expected):
            assert lib.r6_neon_token(source, len(blob), index, slot,
                                     text, len(text)) == R6_OK
            assert text.value.decode("ascii") == value.decode("ascii")
    print("NeonColor: 6 rows, 18 numeric tokens and 31 source lines match")

    assert lib.r6_neon_row(source, len(blob), 6, ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_neon_token(source, len(blob), 0, 3,
                             text, len(text)) == R6_ERR_ARG
    assert lib.r6_neon_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_neon_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_neon_path(source, len(blob), text, 4) == R6_ERR_BUFFER
    assert lib.r6_neon_token(source, len(blob), 0, 0,
                             text, 3) == R6_ERR_BUFFER
    assert lib.r6_neon_parse(source, len(blob) - 1,
                             ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_neon_parse(source, len(bad),
                             ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 5), (20, 30), (24, 0),
                        (28, 1179), (32, 5), (36, 1), (44, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_neon_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for field, value in ((0, 0), (2, 5), (6, 2), (7, 10)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + 4 * field, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_neon_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, HEADER_SIZE + 24, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_neon_parse(source, len(bad),
                             ctypes.byref(header)) == R6_ERR_FORMAT
    print("NeonColor negatives: bad magic/header/row fields, out-of-range "
          "indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = neo.collect(args.dump)
    check(lib, entry, neo.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
