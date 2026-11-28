"""ctypes checks for the packed MA61 specification inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import spec_ma61_catalog as ma6  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 48
ROW_SIZE = 28
STRING_BASE = HEADER_SIZE + 373 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "string_size",
                 "source_bytes", "lines", "table_start", "table_end",
                 "path_offset", "path_length")
ROW_FIELDS = ("key_offset", "key_length", "literal_offset", "literal_length",
              "kind", "line", "comment")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in ROW_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_spec_ma61_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_spec_ma61_path", [BUF, ctypes.c_size_t, BUF, ctypes.c_size_t]),
        ("r6_spec_ma61_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_spec_ma61_key", [BUF, ctypes.c_size_t, U32, BUF,
                              ctypes.c_size_t]),
        ("r6_spec_ma61_literal", [BUF, ctypes.c_size_t, U32, BUF,
                                  ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    path, size, lines, rows = entry
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_spec_ma61_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 373, len(blob) - STRING_BASE, 139729, 3000, 12, 387,
        struct.unpack_from("<2I", blob, 40)[0],
        struct.unpack_from("<2I", blob, 40)[1]]
    text = ctypes.create_string_buffer(96)
    assert lib.r6_spec_ma61_path(source, len(blob),
                                 text, len(text)) == R6_OK
    assert text.value.decode("ascii") == path
    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_spec_ma61_row(source, len(blob), index,
                                    ctypes.byref(row)) == R6_OK
        raw = struct.unpack_from("<7I", blob, HEADER_SIZE + index * ROW_SIZE)
        assert raw == tuple(getattr(row, name) for name in ROW_FIELDS)
        assert (row.kind, row.line, row.comment) == expected[2:]
        assert lib.r6_spec_ma61_key(source, len(blob), index,
                                    text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_spec_ma61_literal(source, len(blob), index,
                                        text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[1]
    print("MA61: 373 rows, 317 integers, 2 floats, 38 ASCII and 16 skipped literals match")

    assert lib.r6_spec_ma61_row(source, len(blob), 373,
                                ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_spec_ma61_key(source, len(blob), 373,
                                text, len(text)) == R6_ERR_ARG
    assert lib.r6_spec_ma61_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_spec_ma61_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_spec_ma61_path(source, len(blob), text, 4) == R6_ERR_BUFFER
    assert lib.r6_spec_ma61_key(source, len(blob), 0,
                                text, 4) == R6_ERR_BUFFER
    assert lib.r6_spec_ma61_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_spec_ma61_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 372), (20, 0), (24, 139728),
                        (28, 2999), (32, 11), (36, 388), (40, 0), (44, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_spec_ma61_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (2, 0), (4, 4), (5, 0), (6, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_spec_ma61_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    print("MA61 negatives: bad magic/header/row fields, out-of-range "
          "indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = ma6.collect(args.dump)
    check(lib, entry, ma6.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
