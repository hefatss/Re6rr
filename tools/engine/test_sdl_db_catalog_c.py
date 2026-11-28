"""ctypes checks for the packed SDL controller database."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import sdl_db_catalog as sdl  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 48
LINE_SIZE = 16
ROW_SIZE = 32
ROW_BASE = HEADER_SIZE + 1916 * LINE_SIZE
STRING_BASE = ROW_BASE + 1904 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "line_count",
                 "string_size", "source_bytes", "comment_count",
                 "blank_count", "path_offset", "path_length")
LINE_FIELDS = ("text_offset", "text_length", "kind", "line")
ROW_FIELDS = ("id_offset", "id_length", "name_offset", "name_length",
              "platform_offset", "platform_length", "fields", "line")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Line(ctypes.Structure):
    _fields_ = [(name, U32) for name in LINE_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in ROW_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_sdl_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_sdl_path", [BUF, ctypes.c_size_t, BUF, ctypes.c_size_t]),
        ("r6_sdl_line", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Line)]),
        ("r6_sdl_line_text", [BUF, ctypes.c_size_t, U32, BUF,
                              ctypes.c_size_t]),
        ("r6_sdl_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_sdl_field_text", [BUF, ctypes.c_size_t, U32, U32, BUF,
                               ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    path, size, lines, line_rows, row_rows = entry
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_sdl_parse(source, len(blob), ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 1904, 1916, len(blob) - STRING_BASE, 506637, 7, 5,
        struct.unpack_from("<2I", blob, 40)[0],
        struct.unpack_from("<2I", blob, 40)[1]]
    small = ctypes.create_string_buffer(64)
    assert lib.r6_sdl_path(source, len(blob), small, len(small)) == R6_OK
    assert small.value.decode("ascii") == path
    text = ctypes.create_string_buffer(512)
    line = Line()
    for index, expected in enumerate(line_rows):
        assert lib.r6_sdl_line(source, len(blob), index,
                               ctypes.byref(line)) == R6_OK
        raw = struct.unpack_from("<4I", blob, HEADER_SIZE + index * LINE_SIZE)
        assert raw == tuple(getattr(line, name) for name in LINE_FIELDS)
        assert (line.kind, line.line) == (expected[1], expected[2])
        assert lib.r6_sdl_line_text(source, len(blob), index,
                                    text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    row = Row()
    for index, expected in enumerate(row_rows):
        assert lib.r6_sdl_row(source, len(blob), index,
                              ctypes.byref(row)) == R6_OK
        raw = struct.unpack_from("<8I", blob, ROW_BASE + index * ROW_SIZE)
        assert raw == tuple(getattr(row, name) for name in ROW_FIELDS)
        assert row.fields == expected[3] and row.line == expected[4]
        for field, value in enumerate(expected[:3]):
            assert lib.r6_sdl_field_text(source, len(blob), index, field,
                                         text, len(text)) == R6_OK
            assert text.value.decode("ascii") == value
    print("SDL: 1916 lines, 1904 rows, 5 platforms and 7 comments match")

    assert lib.r6_sdl_line(source, len(blob), 1916, ctypes.byref(line)) == R6_ERR_ARG
    assert lib.r6_sdl_row(source, len(blob), 1904, ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_sdl_field_text(source, len(blob), 0, 3,
                                 text, len(text)) == R6_ERR_ARG
    assert lib.r6_sdl_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_sdl_line(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_sdl_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_sdl_path(source, len(blob), small, 4) == R6_ERR_BUFFER
    assert lib.r6_sdl_line_text(source, len(blob), 4,
                                text, 4) == R6_ERR_BUFFER
    assert lib.r6_sdl_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_sdl_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 1903), (20, 1915), (24, 0),
                        (28, 506636), (32, 6), (36, 4), (40, 0), (44, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_sdl_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (2, 3), (3, 1917)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_sdl_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (6, 6), (7, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_sdl_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    print("SDL negatives: bad magic/header/line/row fields, out-of-range "
          "indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = sdl.collect(args.dump)
    check(lib, entry, sdl.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
