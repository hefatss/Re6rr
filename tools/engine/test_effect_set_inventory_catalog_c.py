"""ctypes checks for the packed stage-effect SET_*.lua inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import effect_set_inventory_catalog as efs  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
FILE_SIZE = 44
ROW_SIZE = 16
ROW_BASE = HEADER_SIZE + 300 * FILE_SIZE
STRING_BASE = ROW_BASE + 1899 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "row_count", "string_size",
                 "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "name_offset", "name_length",
               "num_offset", "num_length", "effect_num_offset",
               "effect_num_length", "size", "rows", "row_base")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [("path_offset", U32), ("path_length", U32),
                ("model_offset", U32), ("model_length", U32)]


def configure(lib):
    for name, args in (
        ("r6_effect_set_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_effect_set_file", [BUF, ctypes.c_size_t, U32,
                                ctypes.POINTER(File)]),
        ("r6_effect_set_path", [BUF, ctypes.c_size_t, U32, BUF,
                                ctypes.c_size_t]),
        ("r6_effect_set_name", [BUF, ctypes.c_size_t, U32, BUF,
                                ctypes.c_size_t]),
        ("r6_effect_set_num", [BUF, ctypes.c_size_t, U32, BUF,
                               ctypes.c_size_t]),
        ("r6_effect_set_row", [BUF, ctypes.c_size_t, U32,
                               ctypes.POINTER(Row)]),
        ("r6_effect_set_row_path", [BUF, ctypes.c_size_t, U32, BUF,
                                    ctypes.c_size_t]),
        ("r6_effect_set_row_model", [BUF, ctypes.c_size_t, U32, BUF,
                                     ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_effect_set_parse(source, len(blob),
                                   ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 300, 1899, len(blob) - STRING_BASE, 501917]

    file = File()
    text = ctypes.create_string_buffer(128)
    rows = []
    for index, expected in enumerate(files):
        assert lib.r6_effect_set_file(source, len(blob), index,
                                      ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<11I", blob,
                                 HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.name_offset,
                       file.name_length, file.num_offset, file.num_length,
                       file.effect_num_offset, file.effect_num_length,
                       file.size, file.rows, file.row_base)
        assert (file.size, file.rows) == (expected[1], len(expected[5]))
        assert lib.r6_effect_set_path(source, len(blob), index,
                                      text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_effect_set_name(source, len(blob), index,
                                      text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[2]
        assert lib.r6_effect_set_num(source, len(blob), index,
                                     text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[3]
        rows.extend(expected[5])
    for index, expected in enumerate(rows):
        assert lib.r6_effect_set_row_path(source, len(blob), index,
                                          text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_effect_set_row_model(source, len(blob), index,
                                           text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[1]
    print("Effect sets: 300 files and 1899 path/model rows match the dump")

    assert lib.r6_effect_set_file(source, len(blob), 300,
                                  ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_effect_set_row(source, len(blob), 1899,
                                 ctypes.byref(Row())) == R6_ERR_ARG
    assert lib.r6_effect_set_path(source, len(blob), 300,
                                  text, len(text)) == R6_ERR_ARG
    assert lib.r6_effect_set_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_effect_set_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_effect_set_path(source, len(blob), 0,
                                  text, 4) == R6_ERR_BUFFER
    assert lib.r6_effect_set_parse(source, len(blob) - 1,
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_effect_set_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 299), (16, 1898), (20, 0),
                        (24, 501916)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_effect_set_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 3), (2, 0), (3, 0), (8, 0), (9, 0),
                        (10, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_effect_set_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    offset, _ = struct.unpack_from("<2I", blob, ROW_BASE)
    if offset:
        bad = bytearray(blob)
        bad[offset] = 0x01
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_effect_set_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    print("Effect-set negatives: bad magic/header/file/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = efs.collect(args.dump)
    check(lib, files, efs.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
