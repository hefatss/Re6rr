"""ctypes checks for the packed course-debug TDB inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import debug_tdb_registry_catalog as dtr  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 44
FILE_BASE = HEADER_SIZE
PAIR_BASE = FILE_BASE + 23 * 16
SPAN_BASE = PAIR_BASE + 12087 * 16
STRING_BASE = SPAN_BASE + (10 + 4) * 8
FIELDS = ("version", "file_count", "pair_count", "string_size", "table_bytes",
          "accessor_count", "accessor_size", "blink_count", "blink_size")
FILE_FIELDS = ("path_offset", "path_length", "size", "pairs")
PAIR_FIELDS = ("id", "decimal", "name_offset", "name_length")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Pair(ctypes.Structure):
    _fields_ = [(name, U32) for name in PAIR_FIELDS]


def configure(lib):
    lib.r6_debug_tdb_parse.restype = ctypes.c_int
    lib.r6_debug_tdb_parse.argtypes = [BUF, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_debug_tdb_file.restype = ctypes.c_int
    lib.r6_debug_tdb_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                      ctypes.POINTER(File)]
    lib.r6_debug_tdb_path.restype = ctypes.c_int
    lib.r6_debug_tdb_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                      ctypes.c_size_t]
    lib.r6_debug_tdb_pair.restype = ctypes.c_int
    lib.r6_debug_tdb_pair.argtypes = [BUF, ctypes.c_size_t, U32,
                                      ctypes.POINTER(Pair)]
    lib.r6_debug_tdb_blink.restype = ctypes.c_int
    lib.r6_debug_tdb_blink.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                       ctypes.c_size_t]
    lib.r6_debug_tdb_accessor.restype = ctypes.c_int
    lib.r6_debug_tdb_accessor.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                          ctypes.c_size_t]


def check(lib, collection, blob):
    files, pairs, accessors, blinks, _, _ = collection
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_debug_tdb_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in FIELDS] == [
        1, 23, 12087, len(blob) - STRING_BASE, 603341, 10, 1147, 4, 384]

    file = File()
    path = ctypes.create_string_buffer(128)
    for index, (expected_path, expected_size, group) in enumerate(files):
        assert lib.r6_debug_tdb_file(source, len(blob), index,
                                     ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<4I", blob, FILE_BASE + index * 16)
        assert raw == (file.path_offset, file.path_length, file.size,
                       file.pairs)
        assert (file.size, file.pairs) == (expected_size, len(group))
        assert lib.r6_debug_tdb_path(source, len(blob), index,
                                     path, len(path)) == R6_OK
        assert path.value.decode("ascii") == expected_path

    pair = Pair()
    name = ctypes.create_string_buffer(96)
    for index, expected in enumerate(pairs):
        assert lib.r6_debug_tdb_pair(source, len(blob), index,
                                     ctypes.byref(pair)) == R6_OK
        assert (pair.id, pair.decimal) == expected[::2]
        raw = struct.unpack_from("<4I", blob, PAIR_BASE + index * 16)
        assert raw == (pair.id, pair.decimal, pair.name_offset,
                       pair.name_length)
        offset, length = pair.name_offset, pair.name_length
        assert blob[offset:offset + length].decode("ascii") == expected[1]
    print("Debug TDB: 23 files, 12087 id/name pairs, 4 blink names and 10 "
          "accessors match the dump")

    for index, expected in enumerate(blinks):
        assert lib.r6_debug_tdb_blink(source, len(blob), index,
                                      name, len(name)) == R6_OK
        assert name.value.decode("ascii") == expected
    for index, expected in enumerate(accessors):
        assert lib.r6_debug_tdb_accessor(source, len(blob), index,
                                         name, len(name)) == R6_OK
        assert name.value.decode("ascii") == expected
    print("Debug TDB blink/accessor names verified")

    assert lib.r6_debug_tdb_file(source, len(blob), 23,
                                 ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_debug_tdb_pair(source, len(blob), 12087,
                                 ctypes.byref(pair)) == R6_ERR_ARG
    assert lib.r6_debug_tdb_blink(source, len(blob), 4,
                                  name, len(name)) == R6_ERR_ARG
    assert lib.r6_debug_tdb_accessor(source, len(blob), 10,
                                     name, len(name)) == R6_ERR_ARG
    assert lib.r6_debug_tdb_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_debug_tdb_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_debug_tdb_pair(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_debug_tdb_path(source, len(blob), 0,
                                 path, 4) == R6_ERR_BUFFER
    assert lib.r6_debug_tdb_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_debug_tdb_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 22), (16, 12086), (20, 0), (24, 603340),
                        (28, 9), (32, 1146), (36, 3), (40, 383)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_debug_tdb_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 3), (2, 0), (3, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_debug_tdb_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0x0fffffff), (1, 0), (2, 0), (3, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, PAIR_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_debug_tdb_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    offset, _ = struct.unpack_from("<2I", blob, SPAN_BASE + 4 * 8)
    bad = bytearray(blob)
    bad[offset] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_debug_tdb_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    print("Debug TDB negatives: bad magic/header/file/pair/span fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    collection = dtr.collect(args.dump)
    check(lib, collection, dtr.build(collection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
