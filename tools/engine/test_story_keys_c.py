"""ctypes checks for the packed native story-key inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_engine import R6_OK, load_core  # noqa: E402
import story_keys_catalog as sk  # noqa: E402

R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6


class Catalog(ctypes.Structure):
    _fields_ = [
        ("rows", ctypes.c_void_p), ("strings", ctypes.c_void_p),
        ("native_count", ctypes.c_size_t), ("table_count", ctypes.c_size_t),
        ("msgdb_count", ctypes.c_size_t), ("matched_count", ctypes.c_size_t),
        ("string_count", ctypes.c_size_t),
    ]


def set_argtypes(lib):
    lib.r6_story_keys_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                       ctypes.POINTER(Catalog)]
    lib.r6_story_keys_parse.restype = ctypes.c_int
    lib.r6_story_keys_name.argtypes = [ctypes.POINTER(Catalog),
                                      ctypes.c_size_t, ctypes.c_char_p,
                                      ctypes.c_size_t]
    lib.r6_story_keys_name.restype = ctypes.c_int
    lib.r6_story_keys_find.argtypes = [ctypes.POINTER(Catalog),
                                      ctypes.c_char_p]
    lib.r6_story_keys_find.restype = ctypes.c_int
    lib.r6_story_keys_fact.argtypes = [ctypes.POINTER(Catalog),
                                      ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_story_keys_fact.restype = ctypes.c_int


def source(lib, blob):
    return ctypes.create_string_buffer(blob, len(blob))


def check_corpus(lib, data, blob):
    catalog = Catalog()
    assert lib.r6_story_keys_parse(source(lib, blob), len(blob),
                                   ctypes.byref(catalog)) == R6_OK
    assert (catalog.native_count, catalog.table_count, catalog.msgdb_count,
            catalog.matched_count) == (
        len(data["rows"]), sk.TABLE_COUNT, data["msgdb_count"],
        data["matched"])
    text = ctypes.create_string_buffer(64)
    source_value = ctypes.c_uint32()
    table_index = ctypes.c_uint32()
    for index, row in enumerate(data["rows"]):
        assert lib.r6_story_keys_name(
            ctypes.byref(catalog), index, text, len(text)) == R6_OK
        assert text.value.decode("ascii") == row["name"]
        assert lib.r6_story_keys_find(ctypes.byref(catalog),
                                      row["name"].encode("ascii")) == index
        assert lib.r6_story_keys_fact(
            ctypes.byref(catalog), index, ctypes.byref(source_value),
            ctypes.byref(table_index)) == R6_OK
        assert source_value.value == row["source"]
        assert table_index.value == row["table_index"]
    assert lib.r6_story_keys_find(ctypes.byref(catalog),
                                  b"drive_story_NOPE") == -1
    assert lib.r6_story_keys_find(ctypes.byref(catalog), None) == -1
    print("story keys: %d native (%d direct, %d table), %d/%d msgdb keys "
          "present, all names and facts match" %
          (len(data["rows"]), len(sk.DIRECT_KEYS), sk.TABLE_COUNT,
           data["matched"], data["msgdb_count"]))


def check_negative(lib, blob):
    catalog = Catalog()
    bad = bytearray(blob)
    bad[0] = ord("X")
    assert lib.r6_story_keys_parse(source(lib, bytes(bad)), len(bad),
                                   ctypes.byref(catalog)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 8, 2)
    assert lib.r6_story_keys_parse(source(lib, bytes(bad)), len(bad),
                                   ctypes.byref(catalog)) == R6_ERR_FORMAT
    for offset, value in ((24, 102), (32, 0),
                          (sk.HEADER_SIZE + 6, 3),
                          (sk.HEADER_SIZE + 8, 100)):
        bad = bytearray(blob)
        if offset in (24, 32, sk.HEADER_SIZE + 8):
            struct.pack_into("<I", bad, offset, value)
        else:
            bad[offset] = value
        assert lib.r6_story_keys_parse(source(lib, bytes(bad)), len(bad),
                                       ctypes.byref(catalog)) == R6_ERR_FORMAT
    assert lib.r6_story_keys_parse(source(lib, blob[:-1]), len(blob) - 1,
                                   ctypes.byref(catalog)) == R6_ERR_FORMAT
    assert lib.r6_story_keys_parse(None, len(blob),
                                   ctypes.byref(catalog)) == R6_ERR_ARG
    assert lib.r6_story_keys_parse(source(lib, blob), len(blob),
                                   None) == R6_ERR_ARG
    assert lib.r6_story_keys_parse(source(lib, blob), len(blob),
                                   ctypes.byref(catalog)) == R6_OK
    text = ctypes.create_string_buffer(4)
    assert lib.r6_story_keys_name(
        ctypes.byref(catalog), 0, text, len(text)) == R6_ERR_BUFFER
    assert lib.r6_story_keys_name(
        ctypes.byref(catalog), 101, text, 64) == R6_ERR_ARG
    assert lib.r6_story_keys_fact(
        ctypes.byref(catalog), 101, None, None) == R6_ERR_ARG
    print("story key negatives: bad magic/version/counts/offset/source/table, "
          "truncation, null input/output and short buffer rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=os.path.join(
        r"D:\Games\W6W-05", "wmn6r.exe"))
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    set_argtypes(lib)
    data = sk.collect(args.exe, args.dump)
    blob = sk.build(data)
    check_corpus(lib, data, blob)
    check_negative(lib, blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
