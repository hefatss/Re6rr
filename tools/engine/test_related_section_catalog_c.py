"""ctypes checks for the packed related-section inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import related_section_catalog as rsc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
FILE_SIZE = 24
STRING_BASE = HEADER_SIZE + 5 * FILE_SIZE
HEADER_FIELDS = ("version", "file_count", "string_size", "pair_count",
                 "load_speed_0", "load_speed_1")
FILE_FIELDS = ("path_offset", "path_length", "size", "pairs",
               "load_speed_0", "load_speed_1")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Pair(ctypes.Structure):
    _fields_ = [("values", U32 * 12)]


def configure(lib):
    lib.r6_related_parse.restype = ctypes.c_int
    lib.r6_related_parse.argtypes = [BUF, ctypes.c_size_t,
                                     ctypes.POINTER(Header)]
    lib.r6_related_file.restype = ctypes.c_int
    lib.r6_related_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                    ctypes.POINTER(File)]
    lib.r6_related_path.restype = ctypes.c_int
    lib.r6_related_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                    ctypes.c_size_t]
    lib.r6_related_pair.restype = ctypes.c_int
    lib.r6_related_pair.argtypes = [BUF, ctypes.c_size_t, U32,
                                    ctypes.POINTER(Pair)]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_related_parse(source, len(blob),
                                ctypes.byref(header)) == R6_OK
    expected_pairs = [pair for _, _, _, group in rows for pair in group]
    string_size = len(blob) - STRING_BASE - len(expected_pairs) * 48
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 5, string_size, 540, 5, 5]

    file = File()
    path = ctypes.create_string_buffer(128)
    for index, (expected_path, expected_size, load, group) in enumerate(rows):
        assert lib.r6_related_file(source, len(blob), index,
                                   ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<6I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.size,
                       file.pairs, file.load_speed_0, file.load_speed_1)
        assert (file.size, file.pairs) == (expected_size, len(group))
        assert (file.load_speed_0, file.load_speed_1) == load
        assert lib.r6_related_path(source, len(blob), index,
                                   path, len(path)) == R6_OK
        assert path.value.decode("ascii") == expected_path

    pair = Pair()
    for index, expected in enumerate(expected_pairs):
        assert lib.r6_related_pair(source, len(blob), index,
                                   ctypes.byref(pair)) == R6_OK
        assert list(pair.values) == list(expected)
    print("Related sections: 5 files, 540 integer row pairs and paths match "
          "the dump")

    assert lib.r6_related_file(source, len(blob), 5,
                               ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_related_path(source, len(blob), 5,
                               path, len(path)) == R6_ERR_ARG
    assert lib.r6_related_pair(source, len(blob), 540,
                               ctypes.byref(pair)) == R6_ERR_ARG
    assert lib.r6_related_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_related_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_related_pair(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_related_path(source, len(blob), 0,
                               path, 4) == R6_ERR_BUFFER
    assert lib.r6_related_parse(source, len(blob) - 1,
                                ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_related_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 4), (16, 0), (20, 539), (24, 4),
                        (28, 4)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_related_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((4, 0), (12, 3), (12, 200)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_related_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, STRING_BASE + 540 * 48, 605)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_related_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    print("Related-section negatives: bad magic/header/file/pair fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = rsc.collect(args.dump)
    check(lib, rows, rsc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
