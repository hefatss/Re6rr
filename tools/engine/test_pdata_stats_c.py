"""Check the C .pdata statistics reader against pdata.json."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import pdata_stats_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
BUCKET_OFF = 64
FUNC_OFF = BUCKET_OFF + 7 * 8
STRINGS_OFF = FUNC_OFF + 20 * 40

FIELDS = ("version", "function_count", "code_bytes", "text_bytes", "leaf",
          "chained", "with_eh", "min_size", "max_size", "median",
          "bucket_count", "largest_count", "strings_size", "strings_off")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_pdata_stats_parse.restype = ctypes.c_int
    lib.r6_pdata_stats_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_pdata_stats_bucket.restype = ctypes.c_int
    lib.r6_pdata_stats_bucket.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t, PU32]
    lib.r6_pdata_stats_largest.restype = ctypes.c_int
    lib.r6_pdata_stats_largest.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32, PU32, PU32, PU32,
        PU32, PU32, PU32, PU32, BUF, ctypes.c_size_t]
    lib.r6_pdata_stats_find.restype = ctypes.c_int
    lib.r6_pdata_stats_find.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32]


def check(lib):
    configure(lib)
    data, buckets, largest = pdata_stats_catalog.collect()
    blob = pdata_stats_catalog.build(data, buckets, largest)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_pdata_stats_parse(source, len(blob),
                                    ctypes.byref(header)) == R6_OK
    expected = (1, data["functions"], data["code_bytes"], data["text_bytes"],
                data["leaf"], data["chained"], data["with_eh"], data["min"],
                data["max"], data["median"], len(buckets), len(largest))
    assert tuple(getattr(header, field) for field in FIELDS[:12]) == expected
    assert header.strings_off == STRINGS_OFF
    assert header.strings_size == len(blob) - STRINGS_OFF

    label = ctypes.create_string_buffer(32)
    count = U32()
    for index, (expected_label, expected_count) in enumerate(buckets):
        assert lib.r6_pdata_stats_bucket(
            source, len(blob), index, label, len(label),
            ctypes.byref(count)) == R6_OK
        assert label.value.decode("ascii") == expected_label
        assert count.value == expected_count

    begin = U32()
    end = U32()
    size = U32()
    unwind = U32()
    flags = U32()
    leaf = U32()
    chain_begin = U32()
    chain_end = U32()
    chain_unwind = U32()
    section = ctypes.create_string_buffer(32)
    for index, row in enumerate(largest):
        assert lib.r6_pdata_stats_largest(
            source, len(blob), index, ctypes.byref(begin), ctypes.byref(end),
            ctypes.byref(size), ctypes.byref(unwind), ctypes.byref(flags),
            ctypes.byref(leaf), ctypes.byref(chain_begin),
            ctypes.byref(chain_end), ctypes.byref(chain_unwind), section,
            len(section)) == R6_OK
        chain = row["chain"] or {}
        assert (begin.value, end.value, size.value) == \
            (row["begin"], row["end"], row["size"])
        assert unwind.value == row["unwind_rva"]
        assert flags.value == row["flags"]
        assert leaf.value == (1 if row["leaf"] else 0)
        assert chain_begin.value == pdata_stats_catalog.hex_or_none(
            chain.get("begin"))
        assert chain_end.value == pdata_stats_catalog.hex_or_none(
            chain.get("end"))
        assert chain_unwind.value == pdata_stats_catalog.hex_or_none(
            chain.get("unwind"))
        assert section.value.decode("ascii") == row["section"]

    index = U32()
    assert lib.r6_pdata_stats_find(
        source, len(blob), largest[0]["begin"],
        ctypes.byref(index)) == R6_OK
    assert index.value == 0
    assert lib.r6_pdata_stats_find(
        source, len(blob), 0xffffffff,
        ctypes.byref(index)) == R6_ERR_NOT_FOUND

    assert lib.r6_pdata_stats_bucket(
        source, len(blob), 7, label, len(label),
        ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_pdata_stats_largest(
        source, len(blob), 20, ctypes.byref(begin), ctypes.byref(end),
        ctypes.byref(size), ctypes.byref(unwind), ctypes.byref(flags),
        ctypes.byref(leaf), ctypes.byref(chain_begin), ctypes.byref(chain_end),
        ctypes.byref(chain_unwind), section, len(section)) == R6_ERR_ARG
    assert lib.r6_pdata_stats_bucket(
        source, len(blob), 0, label, 2,
        ctypes.byref(count)) == R6_ERR_BUFFER
    assert lib.r6_pdata_stats_parse(source, len(blob) - 1,
                                    ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pdata_stats_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, 48, 8)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pdata_stats_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, FUNC_OFF + 8, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pdata_stats_largest(
        source, len(bad), 0, ctypes.byref(begin), ctypes.byref(end),
        ctypes.byref(size), ctypes.byref(unwind), ctypes.byref(flags),
        ctypes.byref(leaf), ctypes.byref(chain_begin), ctypes.byref(chain_end),
        ctypes.byref(chain_unwind), section, len(section)) == R6_ERR_FORMAT
    print(".pdata stats: 7 buckets and 20 largest functions match pdata.json; "
          "find, bad blob, index, row and capacity rejected")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
