"""ctypes checks for the packed AMCUS INI key inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import amcus_ini_keys_catalog as aik  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 48
FILE_SIZE = 20
LINE_SIZE = 24
LINE_BASE = HEADER_SIZE + 3 * FILE_SIZE
STRING_BASE = LINE_BASE + 204 * LINE_SIZE
HEADER_FIELDS = ("version", "file_count", "line_count", "string_size",
                 "source_bytes", "section_count", "key_count",
                 "comment_count", "blank_count", "reserved")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines", "line_base")
LINE_FIELDS = ("name_offset", "name_length", "kind", "line", "value_present",
               "section")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Line(ctypes.Structure):
    _fields_ = [(name, U32) for name in LINE_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_amcus_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_amcus_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_amcus_path", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_amcus_line", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Line)]),
        ("r6_amcus_name", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, lines, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_amcus_parse(source, len(blob),
                              ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 3, 204, len(blob) - STRING_BASE, 5139, 22, 139, 23, 20, 0]
    text = ctypes.create_string_buffer(96)
    file = File()
    for index, expected in enumerate(files):
        assert lib.r6_amcus_file(source, len(blob), index,
                                 ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<5I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.lines, file.line_base) == expected[1:]
        assert lib.r6_amcus_path(source, len(blob), index,
                                 text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    line = Line()
    for index, expected in enumerate(lines):
        assert lib.r6_amcus_line(source, len(blob), index,
                                 ctypes.byref(line)) == R6_OK
        raw = struct.unpack_from("<6I", blob, LINE_BASE + index * LINE_SIZE)
        assert raw == tuple(getattr(line, name) for name in LINE_FIELDS)
        assert (line.kind, line.line, line.value_present, line.section) == \
            expected[1:]
        assert lib.r6_amcus_name(source, len(blob), index,
                                 text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    print("AMCUS INI: 3 files, 22 sections, 139 keys and 23 comments match")

    assert lib.r6_amcus_file(source, len(blob), 3, ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_amcus_path(source, len(blob), 3, text, len(text)) == R6_ERR_ARG
    assert lib.r6_amcus_line(source, len(blob), 204, ctypes.byref(line)) == R6_ERR_ARG
    assert lib.r6_amcus_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_amcus_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_amcus_line(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_amcus_path(source, len(blob), 0, text, 4) == R6_ERR_BUFFER
    assert lib.r6_amcus_parse(source, len(blob) - 1,
                              ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_amcus_parse(source, len(bad),
                              ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 203), (20, 0), (24, 5138),
                        (28, 21), (32, 138), (36, 22), (40, 19), (44, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_amcus_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 2425), (3, 95), (4, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_amcus_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (2, 4), (3, 205), (4, 2), (5, 23)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, LINE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_amcus_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    print("AMCUS INI negatives: bad magic/header/file/line fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, lines = aik.collect(args.dump)
    check(lib, files, lines, aik.build(files, lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
