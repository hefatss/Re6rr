"""ctypes checks for the packed car vinyl blend table inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import color_vinyl_blend_catalog as cvb  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 44
FILE_SIZE = 16
ROW_SIZE = 20
FUNC_SIZE = 12
ROW_BASE = HEADER_SIZE + FILE_SIZE
FUNC_BASE = ROW_BASE + 62 * ROW_SIZE
STRING_BASE = FUNC_BASE + 4 * FUNC_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "token_count",
                 "line_count", "string_size", "source_bytes",
                 "function_count", "reserved")
ROW_FIELDS = ("name_offset", "name_length", "line", "token_offset",
              "token_count")
FUNC_FIELDS = ("name_offset", "name_length", "line")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in ROW_FIELDS]


class Function(ctypes.Structure):
    _fields_ = [(name, U32) for name in FUNC_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_cvb_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_cvb_path", [BUF, ctypes.c_size_t, BUF, ctypes.c_size_t]),
        ("r6_cvb_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_cvb_token", [BUF, ctypes.c_size_t, U32, U32, BUF,
                          ctypes.c_size_t]),
        ("r6_cvb_function", [BUF, ctypes.c_size_t, U32,
                             ctypes.POINTER(Function)]),
        ("r6_cvb_function_name", [BUF, ctypes.c_size_t, U32, BUF,
                                  ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, rows, functions, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_cvb_parse(source, len(blob),
                            ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 62, 122, 165, len(blob) - STRING_BASE, 8579, 4, 0]
    raw = struct.unpack_from("<4I", blob, HEADER_SIZE)
    assert raw[1:] == (len(cvb.RELATIVE), 8579, 165)
    text = ctypes.create_string_buffer(96)
    assert lib.r6_cvb_path(source, len(blob), text, len(text)) == R6_OK
    assert text.value.decode("ascii") == cvb.RELATIVE
    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_cvb_row(source, len(blob), index,
                              ctypes.byref(row)) == R6_OK
        packed = struct.unpack_from("<5I", blob, ROW_BASE + index * ROW_SIZE)
        assert packed == tuple(getattr(row, name) for name in ROW_FIELDS)
        assert row.line == expected[1] and row.token_count == len(expected[2])
        assert lib.r6_cvb_token(source, len(blob), index, 0,
                                text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[2][0].decode("ascii")
        if row.token_count > 1:
            assert lib.r6_cvb_token(source, len(blob), index, 1,
                                    text, len(text)) == R6_OK
            assert text.value.decode("ascii") == expected[2][1].decode("ascii")
    function = Function()
    for index, expected in enumerate(functions):
        assert lib.r6_cvb_function(source, len(blob), index,
                                   ctypes.byref(function)) == R6_OK
        packed = struct.unpack_from("<3I", blob,
                                    FUNC_BASE + index * FUNC_SIZE)
        assert packed == tuple(getattr(function, name)
                               for name in FUNC_FIELDS)
        assert function.line == expected[1]
        assert lib.r6_cvb_function_name(source, len(blob), index,
                                        text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    print("Car vinyl blend: 62 rows, 122 tokens and 4 functions match")

    assert lib.r6_cvb_row(source, len(blob), 62, ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_cvb_function(source, len(blob), 4,
                               ctypes.byref(function)) == R6_ERR_ARG
    assert lib.r6_cvb_token(source, len(blob), 0, 1,
                            text, len(text)) == R6_ERR_ARG
    assert lib.r6_cvb_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_cvb_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_cvb_path(source, len(blob), text, 4) == R6_ERR_BUFFER
    assert lib.r6_cvb_token(source, len(blob), 0, 0,
                            text, 2) == R6_ERR_BUFFER
    assert lib.r6_cvb_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_cvb_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 61), (20, 121), (24, 164),
                        (28, 0), (32, 8578), (36, 3), (40, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_cvb_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 8578), (3, 164)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_cvb_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 14), (4, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_cvb_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 105)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FUNC_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_cvb_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    print("Car vinyl blend negatives: bad magic/header/file/row/function "
          "fields, out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows, functions = cvb.collect(args.dump)
    check(lib, rows, functions, cvb.build(rows, functions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
