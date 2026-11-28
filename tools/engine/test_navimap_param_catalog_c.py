"""ctypes checks for the packed NavimapParam.lua inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import navimap_param_catalog as nvm  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 48
SCALAR_SIZE = 20
VALUE_BASE = HEADER_SIZE + 4 * SCALAR_SIZE
STRING_BASE = VALUE_BASE + 11 * 8
HEADER_FIELDS = ("version", "string_size", "source_bytes", "source_lines",
                 "scalar_count", "table_count", "path_offset", "path_length",
                 "table_name_offset", "table_name_length")
SCALAR_FIELDS = ("name_offset", "name_length", "value_offset",
                 "value_length", "active")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Scalar(ctypes.Structure):
    _fields_ = [(name, U32) for name in SCALAR_FIELDS]


def configure(lib):
    for name, restype, args in (
        ("r6_navimap_parse", ctypes.c_int, [BUF, ctypes.c_size_t,
                                            ctypes.POINTER(Header)]),
        ("r6_navimap_scalar", ctypes.c_int, [BUF, ctypes.c_size_t, U32,
                                             ctypes.POINTER(Scalar)]),
        ("r6_navimap_path", ctypes.c_int, [BUF, ctypes.c_size_t, BUF,
                                           ctypes.c_size_t]),
        ("r6_navimap_table_name", ctypes.c_int, [BUF, ctypes.c_size_t, BUF,
                                                 ctypes.c_size_t]),
        ("r6_navimap_scalar_name", ctypes.c_int, [BUF, ctypes.c_size_t, U32,
                                                  BUF, ctypes.c_size_t]),
        ("r6_navimap_scalar_value", ctypes.c_int, [BUF, ctypes.c_size_t, U32,
                                                   BUF, ctypes.c_size_t]),
        ("r6_navimap_table_value", ctypes.c_int, [BUF, ctypes.c_size_t, U32,
                                                  BUF, ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = restype
        func.argtypes = args


def check(lib, scalars, values, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_navimap_parse(source, len(blob),
                                ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS][:6] == [
        1, len(blob) - STRING_BASE, 1137, 32, 4, 11]
    text = ctypes.create_string_buffer(96)
    assert lib.r6_navimap_path(source, len(blob), text, len(text)) == R6_OK
    assert text.value.decode("ascii") == nvm.SOURCE
    assert lib.r6_navimap_table_name(source, len(blob), text,
                                     len(text)) == R6_OK
    assert text.value.decode("ascii") == "NAVIMAP_USE"

    scalar = Scalar()
    for index, expected in enumerate(scalars):
        assert lib.r6_navimap_scalar(source, len(blob), index,
                                     ctypes.byref(scalar)) == R6_OK
        raw = struct.unpack_from("<5I", blob,
                                 HEADER_SIZE + index * SCALAR_SIZE)
        assert raw == (scalar.name_offset, scalar.name_length,
                       scalar.value_offset, scalar.value_length,
                       scalar.active)
        assert (scalar.active,) == expected[2:]
        assert lib.r6_navimap_scalar_name(source, len(blob), index,
                                          text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_navimap_scalar_value(source, len(blob), index,
                                           text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[1]
    for index, expected in enumerate(values):
        assert lib.r6_navimap_table_value(source, len(blob), index,
                                          text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
    print("NavimapParam.lua: source path, 4 scalars and 11 table values "
          "match the dump")

    assert lib.r6_navimap_scalar(source, len(blob), 4,
                                 ctypes.byref(scalar)) == R6_ERR_ARG
    assert lib.r6_navimap_scalar_name(source, len(blob), 4,
                                      text, len(text)) == R6_ERR_ARG
    assert lib.r6_navimap_table_value(source, len(blob), 11,
                                      text, len(text)) == R6_ERR_ARG
    assert lib.r6_navimap_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_navimap_scalar(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_navimap_scalar_name(source, len(blob), 0,
                                      text, 4) == R6_ERR_BUFFER
    assert lib.r6_navimap_parse(source, len(blob) - 1,
                                ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_navimap_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 0), (16, 1136), (20, 31), (24, 3),
                        (28, 10), (32, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_navimap_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 0), (4, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_navimap_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    offset = struct.unpack_from("<I", blob, VALUE_BASE)[0]
    bad = bytearray(blob)
    bad[offset] = ord("x")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_navimap_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    print("NavimapParam negatives: bad magic/header/scalar/table fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    scalars, values = nvm.collect(args.dump)
    check(lib, scalars, values, nvm.build(scalars, values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
