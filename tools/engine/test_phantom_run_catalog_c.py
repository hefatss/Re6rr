"""ctypes checks for the packed phantom run inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import phantom_run_catalog as phm  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
U32 = ctypes.c_uint32
U64 = ctypes.c_uint64
BUF = ctypes.c_char_p
HEADER_SIZE = 52
TIMESTAMP_BASE = HEADER_SIZE
RECORD_BASE = TIMESTAMP_BASE + 5 * 8
HEADER_FIELDS = ("version", "file_count", "record_count", "timestamp_count",
                 "source_bytes")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS] + [("words", U32 * 6)]


def configure(lib):
    for name, args in (
        ("r6_phantom_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_phantom_timestamp", [BUF, ctypes.c_size_t, U32,
                                  ctypes.POINTER(U64)]),
        ("r6_phantom_record", [BUF, ctypes.c_size_t, U32,
                               ctypes.POINTER(U64)])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    path, size, words, timestamps, records = entry
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_phantom_parse(source, len(blob),
                                ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 2333, 5, 18728]
    assert list(header.words) == list(words)
    value = U64()
    for index, expected in enumerate(timestamps):
        assert lib.r6_phantom_timestamp(source, len(blob), index,
                                        ctypes.byref(value)) == R6_OK
        assert value.value == expected
        assert struct.unpack_from("<Q", blob, TIMESTAMP_BASE + index * 8)[0] == \
            expected
    for index, expected in enumerate(records):
        assert lib.r6_phantom_record(source, len(blob), index,
                                     ctypes.byref(value)) == R6_OK
        assert value.value == expected
        assert struct.unpack_from("<Q", blob, RECORD_BASE + index * 8)[0] == \
            expected
    print("Phantom: 6 header words, 5 timestamps and 2333 records match")

    assert lib.r6_phantom_timestamp(source, len(blob), 5,
                                    ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_phantom_record(source, len(blob), 2333,
                                 ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_phantom_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_phantom_timestamp(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_phantom_record(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_phantom_parse(source, len(blob) - 1,
                                ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_phantom_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, field, value in ((8, None, 2), (12, None, 2), (16, None, 2332),
                               (20, None, 4), (24, None, 18727),
                               (28, 0, 1573407), (32, 1, 0), (36, 2, 12),
                               (40, 3, 20), (44, 4, 4), (48, 5, 310)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_phantom_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    print("Phantom negatives: bad magic/header fields, out-of-range indexes, "
          "truncation and null outputs rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = phm.collect(args.dump)
    check(lib, entry, phm.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
