"""ctypes checks for the complete drive_story_* key namespace."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_key_namespace_catalog as skn  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("count", U32), ("native_count", U32),
                ("string_size", U32), ("header_size", U32),
                ("strings_offset", U32), ("reserved", U32)]


def configure(lib):
    lib.r6_story_key_namespace_parse.restype = ctypes.c_int
    lib.r6_story_key_namespace_parse.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_story_key_namespace_name.restype = ctypes.c_int
    lib.r6_story_key_namespace_name.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, U32, ctypes.c_char_p,
        ctypes.c_size_t]
    lib.r6_story_key_namespace_find.restype = ctypes.c_int
    lib.r6_story_key_namespace_find.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
    lib.r6_story_key_namespace_fact.restype = ctypes.c_int
    lib.r6_story_key_namespace_fact.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, U32, ctypes.POINTER(U32),
        ctypes.POINTER(U32)]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_story_key_namespace_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.count, header.native_count,
            header.header_size, header.strings_offset, header.reserved) == (
        1, len(rows), 101, 36, 36 + len(rows) * 20, 0)
    assert header.string_size == len(blob) - header.strings_offset

    name = ctypes.create_string_buffer(128)
    src = U32()
    table = U32()
    sources = {}
    for index, row in enumerate(rows):
        assert lib.r6_story_key_namespace_name(
            source, len(blob), index, name, len(name)) == R6_OK
        assert name.value.decode("ascii") == row["name"]
        assert lib.r6_story_key_namespace_find(
            source, len(blob), row["name"].encode("ascii")) == index
        assert lib.r6_story_key_namespace_fact(
            source, len(blob), index, ctypes.byref(src),
            ctypes.byref(table)) == R6_OK
        assert (src.value, table.value) == (
            row["source"], row["table_index"])
        sources[row["source"]] = sources.get(row["source"], 0) + 1
    assert sources == {0: 546, 1: 1, 2: 100}
    assert lib.r6_story_key_namespace_find(
        source, len(blob), b"drive_story_missing") == -1
    print("Story key namespace: all 647 msgdb keys, 101 native sources and "
          "546 msgdb-only keys match the dump")

    assert lib.r6_story_key_namespace_name(
        source, len(blob), len(rows), name, len(name)) == R6_ERR_ARG
    assert lib.r6_story_key_namespace_fact(
        source, len(blob), len(rows), ctypes.byref(src),
        ctypes.byref(table)) == R6_ERR_ARG
    assert lib.r6_story_key_namespace_find(
        source, len(blob), None) == -1
    assert lib.r6_story_key_namespace_name(
        source, len(blob), 0, name, 4) == R6_ERR_BUFFER
    assert lib.r6_story_key_namespace_fact(
        source, len(blob), 0, None, ctypes.byref(table)) == R6_ERR_ARG
    assert lib.r6_story_key_namespace_parse(
        source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_story_key_namespace_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_story_key_namespace_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 646), (16, 648), (20, 1),
                        (24, 35), (28, 37), (32, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_story_key_namespace_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 36, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_story_key_namespace_name(
        source, len(bad), 0, name, len(name)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[36 + 8] = 3
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_story_key_namespace_fact(
        source, len(bad), 0, ctypes.byref(src),
        ctypes.byref(table)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 36 + 12, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    direct = next(i for i, row in enumerate(rows)
                  if row["source"] == 1)
    assert lib.r6_story_key_namespace_fact(
        source, len(bad), direct, ctypes.byref(src),
        ctypes.byref(table)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 36 + 20 * 1 + 12, 100)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_story_key_namespace_fact(
        source, len(bad), 1, ctypes.byref(src),
        ctypes.byref(table)) == R6_ERR_FORMAT
    print("Story key negatives: bad magic/header/sources/table indices, "
          "truncation, bad offsets, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=os.path.join(
        r"D:\Games\W6W-05", "wmn6r.exe"))
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = skn.collect(args.exe, args.dump)
    check(lib, rows, skn.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
