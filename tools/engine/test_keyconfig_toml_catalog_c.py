"""ctypes checks for the packed keyconfig.toml inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import keyconfig_toml_catalog as key  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 48
LINE_SIZE = 16
STRING_BASE = HEADER_SIZE + 39 * LINE_SIZE
HEADER_FIELDS = ("version", "file_count", "line_count", "string_size",
                 "source_bytes", "active_count", "comment_count",
                 "blank_count", "path_offset", "path_length")
LINE_FIELDS = ("text_offset", "text_length", "kind", "line")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Line(ctypes.Structure):
    _fields_ = [(name, U32) for name in LINE_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_keyconfig_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_keyconfig_path", [BUF, ctypes.c_size_t, BUF, ctypes.c_size_t]),
        ("r6_keyconfig_line", [BUF, ctypes.c_size_t, U32,
                               ctypes.POINTER(Line)]),
        ("r6_keyconfig_text", [BUF, ctypes.c_size_t, U32, BUF,
                               ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    path, size, lines, rows = entry
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_keyconfig_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 39, len(blob) - STRING_BASE, 1106, 22, 13, 4,
        struct.unpack_from("<2I", blob, 40)[0],
        struct.unpack_from("<2I", blob, 40)[1]]
    small = ctypes.create_string_buffer(64)
    assert lib.r6_keyconfig_path(source, len(blob),
                                 small, len(small)) == R6_OK
    assert small.value.decode("ascii") == path
    text = ctypes.create_string_buffer(128)
    line = Line()
    for index, expected in enumerate(rows):
        assert lib.r6_keyconfig_line(source, len(blob), index,
                                     ctypes.byref(line)) == R6_OK
        raw = struct.unpack_from("<4I", blob, HEADER_SIZE + index * LINE_SIZE)
        assert raw == tuple(getattr(line, name) for name in LINE_FIELDS)
        assert (line.kind, line.line) == (expected[1], expected[2])
        assert lib.r6_keyconfig_text(source, len(blob), index,
                                     text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    print("Keyconfig: 39 lines, 22 active, 13 comments and 4 blanks match")

    assert lib.r6_keyconfig_line(source, len(blob), 39,
                                 ctypes.byref(line)) == R6_ERR_ARG
    assert lib.r6_keyconfig_text(source, len(blob), 39,
                                 text, len(text)) == R6_ERR_ARG
    assert lib.r6_keyconfig_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_keyconfig_line(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_keyconfig_path(source, len(blob), small, 4) == R6_ERR_BUFFER
    assert lib.r6_keyconfig_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_keyconfig_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 38), (20, 0), (24, 1105),
                        (28, 21), (32, 12), (36, 5), (40, 0), (44, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_keyconfig_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (2, 3), (3, 40)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_keyconfig_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    print("Keyconfig negatives: bad magic/header/line fields, out-of-range "
          "indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = key.collect(args.dump)
    check(lib, entry, key.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
