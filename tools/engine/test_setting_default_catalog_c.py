"""ctypes checks for the packed setting default inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import setting_default_catalog as std  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
ROW_SIZE = 20
ROW_BASE = HEADER_SIZE + 16
STRING_BASE = ROW_BASE + 13 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "string_size",
                 "source_bytes", "lines")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [("name_offset", U32), ("name_length", U32),
                ("value_offset", U32), ("value_length", U32),
                ("active", U32)]


def configure(lib):
    for name, args in (
        ("r6_setting_default_parse", [BUF, ctypes.c_size_t,
                                      ctypes.POINTER(Header)]),
        ("r6_setting_default_path", [BUF, ctypes.c_size_t, BUF,
                                     ctypes.c_size_t]),
        ("r6_setting_default_row", [BUF, ctypes.c_size_t, U32,
                                    ctypes.POINTER(Row)]),
        ("r6_setting_default_name", [BUF, ctypes.c_size_t, U32, BUF,
                                     ctypes.c_size_t]),
        ("r6_setting_default_value", [BUF, ctypes.c_size_t, U32, BUF,
                                      ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_setting_default_parse(source, len(blob),
                                        ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 13, len(blob) - STRING_BASE, 1343, 34]
    text = ctypes.create_string_buffer(96)
    assert lib.r6_setting_default_path(source, len(blob),
                                       text, len(text)) == R6_OK
    assert text.value.decode("ascii") == entry[0]
    row = Row()
    for index, expected in enumerate(entry[3]):
        assert lib.r6_setting_default_row(source, len(blob), index,
                                          ctypes.byref(row)) == R6_OK
        raw = struct.unpack_from("<5I", blob, ROW_BASE + index * ROW_SIZE)
        assert raw == (row.name_offset, row.name_length, row.value_offset,
                       row.value_length, row.active)
        assert (row.active,) == (expected[1],)
        assert lib.r6_setting_default_name(source, len(blob), index,
                                           text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_setting_default_value(source, len(blob), index,
                                            text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[2]
    print("Setting default: 13 rows, 12 active, 8 tokens and 5 hex values match")

    assert lib.r6_setting_default_row(source, len(blob), 13,
                                      ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_setting_default_name(source, len(blob), 13,
                                       text, len(text)) == R6_ERR_ARG
    assert lib.r6_setting_default_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_setting_default_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_setting_default_path(source, len(blob),
                                       text, 4) == R6_ERR_BUFFER
    assert lib.r6_setting_default_parse(source, len(blob) - 1,
                                        ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_setting_default_parse(source, len(bad),
                                        ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 12), (20, 0), (24, 1342),
                        (28, 33)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_setting_default_parse(source, len(bad),
                                            ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 1), (2, 0), (4, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_setting_default_parse(source, len(bad),
                                            ctypes.byref(header)) == R6_ERR_FORMAT
    print("Setting-default negatives: bad magic/header/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = std.collect(args.dump)
    check(lib, entry, std.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
