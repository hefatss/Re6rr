"""ctypes checks for the packed street-lamp layout inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import street_lamp_catalog as slc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
FILE_BASE = HEADER_SIZE
FILE_SIZE = 32
FIELDS = ["path_offset", "path_length", "size", "record_count", "stride",
          "flag_min", "flag_max", "distinct"]


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "version", "file_count", "string_size", "total_bytes",
        "record_count", "stride")]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_street_lamp_parse.restype = ctypes.c_int
    lib.r6_street_lamp_parse.argtypes = [BUF, ctypes.c_size_t,
                                         ctypes.POINTER(Header)]
    lib.r6_street_lamp_file.restype = ctypes.c_int
    lib.r6_street_lamp_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                        ctypes.POINTER(File)]
    lib.r6_street_lamp_path.restype = ctypes.c_int
    lib.r6_street_lamp_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                        ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_street_lamp_parse(source, len(blob),
                                    ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.stride) == (
        1, len(rows), slc.STRIDE)
    assert header.string_size == len(blob) - HEADER_SIZE - len(rows) * FILE_SIZE
    assert (header.total_bytes, header.record_count) == (697648, 24916)

    file = File()
    path = ctypes.create_string_buffer(96)
    for index, row in enumerate(rows):
        fields = struct.unpack_from("<8I", blob, FILE_BASE + index * FILE_SIZE)
        assert lib.r6_street_lamp_file(source, len(blob), index,
                                       ctypes.byref(file)) == R6_OK
        assert lib.r6_street_lamp_path(source, len(blob), index, path,
                                       len(path)) == R6_OK
        assert path.value.decode("ascii") == row[0]
        assert [getattr(file, name) for name in FIELDS] == list(fields)
        assert fields[2:8] == (row[1], row[2], slc.STRIDE, row[3], row[4],
                               row[5])
    print("Street lamps: 168 files, 24916 stride-28 records and copied flag "
          "ranges match the dump")

    assert lib.r6_street_lamp_file(source, len(blob), len(rows),
                                   ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_street_lamp_path(source, len(blob), len(rows), path,
                                   len(path)) == R6_ERR_ARG
    assert lib.r6_street_lamp_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_street_lamp_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_street_lamp_path(source, len(blob), 0, path, 4) == \
        R6_ERR_BUFFER
    assert lib.r6_street_lamp_parse(source, len(blob) - 1,
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_street_lamp_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 167), (16, 1), (20, 697647),
                        (24, 24915), (28, 27)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_street_lamp_parse(source, len(bad),
                                        ctypes.byref(header)) == R6_ERR_FORMAT
    for index, value in ((1, 0), (2, 0), (3, 0), (4, 27), (6, 0), (7, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + index * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_street_lamp_parse(source, len(bad),
                                        ctypes.byref(header)) == R6_ERR_FORMAT
    print("Street-lamp negatives: bad magic/header/file fields, truncation "
          "and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = slc.collect(args.dump)
    check(lib, rows, slc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
