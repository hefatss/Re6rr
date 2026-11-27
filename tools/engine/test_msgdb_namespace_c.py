"""ctypes checks for the complete msgdb.lua MessageID namespace."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import msgdb_namespace_catalog as mnc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("count", U32), ("group_count", U32),
                ("string_size", U32), ("msgdb_size", U32),
                ("story_count", U32)]


def configure(lib):
    lib.r6_msgdb_namespace_parse.restype = ctypes.c_int
    lib.r6_msgdb_namespace_parse.argtypes = [BUF, ctypes.c_size_t,
                                             ctypes.POINTER(Header)]
    lib.r6_msgdb_namespace_key.restype = ctypes.c_int
    lib.r6_msgdb_namespace_key.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                           ctypes.c_size_t]
    lib.r6_msgdb_namespace_find.restype = ctypes.c_int
    lib.r6_msgdb_namespace_find.argtypes = [BUF, ctypes.c_size_t, BUF]
    lib.r6_msgdb_namespace_fact.restype = ctypes.c_int
    lib.r6_msgdb_namespace_fact.argtypes = [BUF, ctypes.c_size_t, U32,
                                            ctypes.POINTER(U32),
                                            ctypes.POINTER(U32)]
    lib.r6_msgdb_namespace_group.restype = ctypes.c_int
    lib.r6_msgdb_namespace_group.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                             ctypes.c_size_t]


def check(lib, rows, groups, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_msgdb_namespace_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.count, header.group_count,
            header.msgdb_size, header.story_count) == (
        1, len(rows), len(groups), mnc.EXPECTED_SIZE, mnc.EXPECTED_STORY)
    assert header.string_size == (len(blob) - 32 - len(rows) * 16 -
                                  len(groups) * 4)

    key = ctypes.create_string_buffer(64)
    group = ctypes.create_string_buffer(8)
    offset = U32()
    group_index = U32()
    for index, (byte_offset, name, index_group) in enumerate(rows):
        assert lib.r6_msgdb_namespace_key(
            source, len(blob), index, key, len(key)) == R6_OK
        assert key.value.decode("ascii") == name
        assert lib.r6_msgdb_namespace_fact(
            source, len(blob), index, ctypes.byref(offset),
            ctypes.byref(group_index)) == R6_OK
        assert (offset.value, group_index.value) == (byte_offset, index_group)
        assert lib.r6_msgdb_namespace_group(
            source, len(blob), index_group, group, len(group)) == R6_OK
        assert group.value.decode("ascii") == groups[index_group]
    for index in list(range(0, len(rows), 64)) + [len(rows) - 1]:
        assert lib.r6_msgdb_namespace_find(
            source, len(blob), rows[index][1].encode("ascii")) == index
    assert lib.r6_msgdb_namespace_find(
        source, len(blob), b"drive_story_missing") == -1
    print("MessageID namespace: all 31021 keys, offsets, groups and 647 "
          "drive_story keys match msgdb.lua")

    assert lib.r6_msgdb_namespace_key(
        source, len(blob), len(rows), key, len(key)) == R6_ERR_ARG
    assert lib.r6_msgdb_namespace_fact(
        source, len(blob), len(rows), ctypes.byref(offset),
        ctypes.byref(group_index)) == R6_ERR_ARG
    assert lib.r6_msgdb_namespace_group(
        source, len(blob), len(groups), group, len(group)) == R6_ERR_ARG
    assert lib.r6_msgdb_namespace_find(
        source, len(blob), None) == -1
    assert lib.r6_msgdb_namespace_key(
        source, len(blob), 0, key, 4) == R6_ERR_BUFFER
    assert lib.r6_msgdb_namespace_group(
        source, len(blob), 0, group, 4) == R6_ERR_BUFFER
    assert lib.r6_msgdb_namespace_fact(
        source, len(blob), 0, None, ctypes.byref(group_index)) == R6_ERR_ARG
    assert lib.r6_msgdb_namespace_parse(
        source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_msgdb_namespace_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_msgdb_namespace_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 31020), (16, 57), (20, 1),
                        (24, rows[-1][0]), (28, 646)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_msgdb_namespace_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 0xffffffff), (12, 1),
                        (16, mnc.EXPECTED_SIZE), (12, 58), (32, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_msgdb_namespace_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 32 + 8, mnc.EXPECTED_SIZE)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_msgdb_namespace_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    print("MessageID negatives: bad magic/header/offsets/groups, truncation, "
          "null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows, groups = mnc.collect(args.dump)
    check(lib, rows, groups, mnc.build(rows, groups))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
