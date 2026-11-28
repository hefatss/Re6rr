"""ctypes checks for the packed DISTCLIP inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import distclip_catalog as dcl  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
FILE_SIZE = 32
ROW_SIZE = 12
ROW_BASE = HEADER_SIZE + 395 * FILE_SIZE
STRING_BASE = ROW_BASE + 3950 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "string_size",
                 "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "table_offset", "table_length",
               "size", "lines", "row_base", "rows")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [("key_offset", U32), ("key_length", U32), ("value", U32)]


def configure(lib):
    for name, args in (
        ("r6_distclip_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_distclip_file", [BUF, ctypes.c_size_t, U32,
                              ctypes.POINTER(File)]),
        ("r6_distclip_path", [BUF, ctypes.c_size_t, U32, BUF,
                              ctypes.c_size_t]),
        ("r6_distclip_table", [BUF, ctypes.c_size_t, U32, BUF,
                               ctypes.c_size_t]),
        ("r6_distclip_row", [BUF, ctypes.c_size_t, U32,
                             ctypes.POINTER(Row)]),
        ("r6_distclip_row_key", [BUF, ctypes.c_size_t, U32, BUF,
                                 ctypes.c_size_t]),
        ("r6_distclip_row_value", [BUF, ctypes.c_size_t, U32,
                                   ctypes.POINTER(U32)])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_distclip_parse(source, len(blob),
                                 ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 395, 3950, len(blob) - STRING_BASE, 83284]

    file = File()
    text = ctypes.create_string_buffer(128)
    rows = []
    for index, expected in enumerate(files):
        assert lib.r6_distclip_file(source, len(blob), index,
                                    ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<8I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.table_offset,
                       file.table_length, file.size, file.lines,
                       file.row_base, file.rows)
        assert (file.size, file.lines, file.rows) == \
            (expected[1], expected[2], len(expected[4]))
        assert lib.r6_distclip_path(source, len(blob), index,
                                    text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_distclip_table(source, len(blob), index,
                                     text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[3]
        rows.extend(expected[4])
    assert len(rows) == 3950
    value = U32()
    for index, expected in enumerate(rows):
        assert lib.r6_distclip_row(source, len(blob), index,
                                   ctypes.byref(Row())) == R6_OK
        assert lib.r6_distclip_row_key(source, len(blob), index,
                                       text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_distclip_row_value(source, len(blob), index,
                                         ctypes.byref(value)) == R6_OK
        assert value.value == expected[1]
    print("DISTCLIP: 395 files, 3950 keys and values match the dump")

    assert lib.r6_distclip_file(source, len(blob), 395,
                                ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_distclip_row(source, len(blob), 3950,
                               ctypes.byref(Row())) == R6_ERR_ARG
    assert lib.r6_distclip_path(source, len(blob), 395,
                                text, len(text)) == R6_ERR_ARG
    assert lib.r6_distclip_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_distclip_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_distclip_row_value(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_distclip_path(source, len(blob), 0,
                                text, 4) == R6_ERR_BUFFER
    assert lib.r6_distclip_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_distclip_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, new in ((8, 2), (12, 394), (16, 3949), (20, 0), (24, 83283)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, new)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_distclip_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, new in ((0, 0), (2, 0), (5, 0), (6, 1), (7, 9)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, new)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_distclip_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, new in ((0, 0), (2, 50001)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, new)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_distclip_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    print("DISTCLIP negatives: bad magic/header/file/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = dcl.collect(args.dump)
    check(lib, files, dcl.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
