"""ctypes checks for the packed playerCar color inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import player_color_catalog as pcc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 40
FILE_SIZE = 28
ROW_SIZE = 16
FILE_BASE = HEADER_SIZE
ROW_BASE = FILE_BASE + 300 * FILE_SIZE
STRING_BASE = ROW_BASE + 6133 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "token_count",
                 "line_count", "source_bytes", "string_size", "reserved")
FILE_FIELDS = ("name_offset", "name_length", "size", "lines", "color_max",
               "start_line", "row_base")
ROW_FIELDS = ("name_offset", "name_length", "line", "token_offset")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in ROW_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_pcc_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_pcc_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_pcc_name", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_pcc_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_pcc_token", [BUF, ctypes.c_size_t, U32, U32, BUF,
                          ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_pcc_parse(source, len(blob),
                            ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 300, 6133, 116527, 166760, 5585086,
        len(blob) - STRING_BASE, 0]
    text = ctypes.create_string_buffer(96)
    file = File()
    for index, expected in enumerate(files):
        assert lib.r6_pcc_file(source, len(blob), index,
                               ctypes.byref(file)) == R6_OK
        packed = struct.unpack_from("<7I", blob, FILE_BASE + index * FILE_SIZE)
        assert packed == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.lines, file.color_max, file.start_line,
                file.row_base) == (expected[1], expected[2], expected[3],
                                   expected[4],
                                   sum(prior[3] for prior in files[:index]))
        assert lib.r6_pcc_name(source, len(blob), index,
                               text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_pcc_row(source, len(blob), index,
                              ctypes.byref(row)) == R6_OK
        packed = struct.unpack_from("<4I", blob, ROW_BASE + index * ROW_SIZE)
        assert packed == tuple(getattr(row, name) for name in ROW_FIELDS)
        assert row.line == expected[1]
        for slot, token in enumerate(expected[2]):
            assert lib.r6_pcc_token(source, len(blob), index, slot,
                                    text, len(text)) == R6_OK
            assert text.value.decode("ascii") == token.decode("ascii")
    print("playerCar colors: 300 files, 6133 blocks and 116527 tokens match")

    assert lib.r6_pcc_file(source, len(blob), 300, ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_pcc_row(source, len(blob), 6133, ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_pcc_token(source, len(blob), 0, 19,
                            text, len(text)) == R6_ERR_ARG
    assert lib.r6_pcc_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_pcc_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_pcc_name(source, len(blob), 0, text, 4) == R6_ERR_BUFFER
    assert lib.r6_pcc_token(source, len(blob), 0, 0,
                            text, 2) == R6_ERR_BUFFER
    assert lib.r6_pcc_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pcc_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 299), (16, 6132), (20, 116526),
                        (24, 166759), (28, 5585085), (32, 0), (36, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_pcc_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 5585085), (3, 0), (4, 0), (5, 41), (6, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_pcc_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((1, 0), (2, 0), (3, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_pcc_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    print("playerCar color negatives: bad magic/header/file/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, rows = pcc.collect(args.dump)
    check(lib, files, rows, pcc.build(files, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
