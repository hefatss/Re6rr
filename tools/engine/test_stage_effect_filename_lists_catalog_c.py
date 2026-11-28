"""ctypes checks for the packed stage-effect filename lists."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import stage_effect_filename_lists_catalog as sfl  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 24
FILE_SIZE = 16
NAME_BASE = HEADER_SIZE + 6 * FILE_SIZE
STRING_BASE = NAME_BASE + 34 * 8
HEADER_FIELDS = ("version", "file_count", "name_count", "string_size")
FILE_FIELDS = ("path_offset", "path_length", "size", "names")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


def configure(lib):
    lib.r6_stage_effect_filename_parse.restype = ctypes.c_int
    lib.r6_stage_effect_filename_parse.argtypes = [BUF, ctypes.c_size_t,
                                                   ctypes.POINTER(Header)]
    lib.r6_stage_effect_filename_file.restype = ctypes.c_int
    lib.r6_stage_effect_filename_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                                  ctypes.POINTER(File)]
    lib.r6_stage_effect_filename_path.restype = ctypes.c_int
    lib.r6_stage_effect_filename_path.argtypes = [BUF, ctypes.c_size_t, U32,
                                                  BUF, ctypes.c_size_t]
    lib.r6_stage_effect_filename_name.restype = ctypes.c_int
    lib.r6_stage_effect_filename_name.argtypes = [BUF, ctypes.c_size_t, U32,
                                                  BUF, ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_stage_effect_filename_parse(source, len(blob),
                                              ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 6, 34, len(blob) - STRING_BASE]

    file = File()
    text = ctypes.create_string_buffer(128)
    for index, (expected_path, expected_size, names) in enumerate(rows):
        assert lib.r6_stage_effect_filename_file(source, len(blob), index,
                                                 ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<4I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.size,
                       file.names)
        assert (file.size, file.names) == (expected_size, len(names))
        assert lib.r6_stage_effect_filename_path(source, len(blob), index,
                                                 text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected_path

    expected_names = [name for _, _, names in rows for name in names]
    for index, expected in enumerate(expected_names):
        assert lib.r6_stage_effect_filename_name(source, len(blob), index,
                                                 text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
        offset, length = struct.unpack_from("<2I", blob, NAME_BASE + index * 8)
        assert blob[offset:offset + length].decode("ascii") == expected
    print("Stage-effect filename lists: 6 paths and 34 .lua names match the "
          "dump")

    assert lib.r6_stage_effect_filename_file(source, len(blob), 6,
                                             ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_stage_effect_filename_path(source, len(blob), 6,
                                             text, len(text)) == R6_ERR_ARG
    assert lib.r6_stage_effect_filename_name(source, len(blob), 34,
                                             text, len(text)) == R6_ERR_ARG
    assert lib.r6_stage_effect_filename_parse(source, len(blob),
                                              None) == R6_ERR_ARG
    assert lib.r6_stage_effect_filename_file(source, len(blob), 0,
                                             None) == R6_ERR_ARG
    assert lib.r6_stage_effect_filename_path(source, len(blob), 0,
                                             text, 4) == R6_ERR_BUFFER
    assert lib.r6_stage_effect_filename_parse(source, len(blob) - 1,
                                              ctypes.byref(header)) == \
        R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_stage_effect_filename_parse(source, len(bad),
                                              ctypes.byref(header)) == \
        R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 5), (16, 33), (20, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_stage_effect_filename_parse(source, len(bad),
                                                  ctypes.byref(header)) == \
            R6_ERR_FORMAT
    for slot, value in ((1, 3), (2, 0), (3, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_stage_effect_filename_parse(source, len(bad),
                                                  ctypes.byref(header)) == \
            R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (1, 250)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, NAME_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_stage_effect_filename_parse(source, len(bad),
                                                  ctypes.byref(header)) == \
            R6_ERR_FORMAT
    print("Stage-effect filename negatives: bad magic/header/file/name "
          "fields, out-of-range indexes, truncation and short buffers "
          "rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = sfl.collect(args.dump)
    check(lib, rows, sfl.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
