"""ctypes checks for the packed stage-effect gzip inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import gz_effect_catalog as gec  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("string_size", U32), ("flag0_count", U32),
                ("flag8_count", U32), ("known_count", U32),
                ("other_count", U32)]


class File(ctypes.Structure):
    _fields_ = [("path_offset", U32), ("path_length", U32),
                ("compressed_size", U32), ("flags", U32),
                ("mtime", U32), ("xfl", U32), ("operating_system", U32),
                ("isize", U32), ("inflated_size", U32),
                ("header_size", U32), ("prefix_length", U32),
                ("prefix", ctypes.c_ubyte * 16)]


def configure(lib):
    lib.r6_gz_effect_parse.restype = ctypes.c_int
    lib.r6_gz_effect_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_gz_effect_file.restype = ctypes.c_int
    lib.r6_gz_effect_file.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                      ctypes.POINTER(File)]
    lib.r6_gz_effect_path.restype = ctypes.c_int
    lib.r6_gz_effect_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                      ctypes.c_char_p, ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_gz_effect_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.flag0_count,
            header.flag8_count, header.known_count, header.other_count) == (
        1, len(rows), gec.EXPECTED_FLAG0, gec.EXPECTED_FLAG8,
        gec.EXPECTED_KNOWN, gec.EXPECTED_OTHER)
    assert header.string_size == len(blob) - 36 - len(rows) * 60

    file = File()
    path = ctypes.create_string_buffer(160)
    for index, row in enumerate(rows):
        assert lib.r6_gz_effect_file(
            source, len(blob), index, ctypes.byref(file)) == R6_OK
        assert file.path_length == len(row[0].encode("ascii"))
        assert (file.compressed_size, file.flags, file.mtime, file.xfl,
                file.operating_system, file.isize, file.inflated_size,
                file.header_size, file.prefix_length) == row[1:10]
        assert bytes(file.prefix) == row[10]
        assert lib.r6_gz_effect_path(
            source, len(blob), index, path, len(path)) == R6_OK
        assert path.value.decode("ascii") == row[0]
    print("Stage-effect gzip catalog: all 1087 files, FLG classes and 16-byte "
          "inflated prefixes match the dump")

    assert lib.r6_gz_effect_file(
        source, len(blob), len(rows), ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_gz_effect_path(
        source, len(blob), len(rows), path, len(path)) == R6_ERR_ARG
    assert lib.r6_gz_effect_file(
        source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_gz_effect_path(
        source, len(blob), 0, None, len(path)) == R6_ERR_ARG
    assert lib.r6_gz_effect_path(
        source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_gz_effect_parse(
        source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_gz_effect_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_gz_effect_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1086), (16, 1), (20, 603),
                        (24, 484), (28, 898), (32, 189)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_gz_effect_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT

    row = 36
    for slot, value in ((4, 0), (12, 1), (28, rows[0][7] + 1),
                        (32, 0), (36, 9), (40, 17)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, row + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_gz_effect_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[row + 44 + rows[0][9]] = ord("Z")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_gz_effect_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    print("Stage-effect gzip negatives: bad magic/header/counts/rows/padding, "
          "truncation, null outputs and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = gec.collect(args.dump)
    check(lib, rows, gec.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
