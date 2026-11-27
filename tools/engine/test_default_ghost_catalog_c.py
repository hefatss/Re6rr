"""ctypes checks for the packed default ghost layout inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import default_ghost_catalog as dgc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 52
FILE_BASE = HEADER_SIZE
FILE_SIZE = 44
FIELDS = ["path_offset", "path_length", "file_size", "record_count", "code",
          "name1_min", "name1_max", "name2_min", "name2_max",
          "tuple_a_count", "tuple_b_count"]


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "version", "file_count", "string_size", "stride", "name1_offset",
        "name1_capacity", "name2_offset", "name2_capacity",
        "tuple_a_offset", "tuple_b_offset", "record_count")]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_default_ghost_parse.restype = ctypes.c_int
    lib.r6_default_ghost_parse.argtypes = [BUF, ctypes.c_size_t,
                                           ctypes.POINTER(Header)]
    lib.r6_default_ghost_file.restype = ctypes.c_int
    lib.r6_default_ghost_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                          ctypes.POINTER(File)]
    lib.r6_default_ghost_path.restype = ctypes.c_int
    lib.r6_default_ghost_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                          ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_default_ghost_parse(source, len(blob),
                                      ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.stride) == (
        1, len(rows), dgc.STRIDE)
    assert header.string_size == len(blob) - HEADER_SIZE - len(rows) * FILE_SIZE
    assert (header.name1_offset, header.name1_capacity,
            header.name2_offset, header.name2_capacity,
            header.tuple_a_offset, header.tuple_b_offset) == (
        dgc.NAME1_OFFSET, dgc.NAME1_CAPACITY, dgc.NAME2_OFFSET,
        dgc.NAME2_CAPACITY, dgc.TUPLE_A_OFFSET, dgc.TUPLE_B_OFFSET)
    assert header.record_count == sum(row[2] for row in rows) == 69056

    file = File()
    path = ctypes.create_string_buffer(96)
    for index, row in enumerate(rows):
        fields = struct.unpack_from("<11I", blob,
                                    FILE_BASE + index * FILE_SIZE)
        assert lib.r6_default_ghost_file(source, len(blob), index,
                                         ctypes.byref(file)) == R6_OK
        assert lib.r6_default_ghost_path(source, len(blob), index, path,
                                         len(path)) == R6_OK
        assert path.value.decode("ascii") == row[0]
        assert [getattr(file, name) for name in FIELDS] == list(fields)
        assert fields[2:6] == row[1:5]
        assert fields[6:11] == row[5:10]
    print("Default ghosts: 9 tables, 69056 stride-136 records and all copied "
          "layout facts match the dump")

    assert lib.r6_default_ghost_file(source, len(blob), len(rows),
                                     ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_default_ghost_path(source, len(blob), len(rows), path,
                                     len(path)) == R6_ERR_ARG
    assert lib.r6_default_ghost_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_default_ghost_file(source, len(blob), 0,
                                     None) == R6_ERR_ARG
    assert lib.r6_default_ghost_path(source, len(blob), 0, path, 4) == \
        R6_ERR_BUFFER
    assert lib.r6_default_ghost_parse(source, len(blob) - 1,
                                      ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_default_ghost_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 8), (16, 1), (20, 135), (24, 9),
                        (28, 15), (32, 97), (36, 27), (40, 83),
                        (44, 127), (48, 69055)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_default_ghost_parse(source, len(bad),
                                          ctypes.byref(header)) == R6_ERR_FORMAT
    for index, value in ((2, 0), (3, 1), (4, 0), (5, 0), (6, 2),
                         (7, 0), (8, 2), (9, 0), (10, 69057)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + index * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_default_ghost_parse(source, len(bad),
                                          ctypes.byref(header)) == R6_ERR_FORMAT
    path_offset, path_length = struct.unpack_from("<2I", blob, FILE_BASE)
    bad = bytearray(blob)
    bad[path_offset + path_length - 1] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_default_ghost_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    print("Default ghost negatives: bad magic/header/file fields, truncation "
          "and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = dgc.collect(args.dump)
    check(lib, rows, dgc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
