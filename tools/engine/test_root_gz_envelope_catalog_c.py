"""ctypes checks for the packed root gzip envelope inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import root_gz_envelope_catalog as rgz  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
FILE_SIZE = 32
STRING_BASE = HEADER_SIZE + 25 * FILE_SIZE
HEADER_FIELDS = ("version", "file_count", "valid_count", "empty_count",
                 "source_bytes", "string_size")
FILE_FIELDS = ("name_offset", "name_length", "size", "mtime", "crc32",
               "isize", "header_flags", "valid")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_root_gz_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_root_gz_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_root_gz_name", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_root_gz_parse(source, len(blob),
                                ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 25, 20, 5, 1239, len(blob) - STRING_BASE]
    text = ctypes.create_string_buffer(96)
    file = File()
    for index, expected in enumerate(rows):
        assert lib.r6_root_gz_file(source, len(blob), index,
                                   ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<8I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.mtime, file.crc32, file.isize,
                file.header_flags, file.valid) == expected[1:]
        assert lib.r6_root_gz_name(source, len(blob), index,
                                   text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    print("Root gzip: 25 envelopes, 20 valid and 5 empty files match")

    assert lib.r6_root_gz_file(source, len(blob), 25,
                               ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_root_gz_name(source, len(blob), 25,
                               text, len(text)) == R6_ERR_ARG
    assert lib.r6_root_gz_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_root_gz_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_root_gz_name(source, len(blob), 0, text, 4) == R6_ERR_BUFFER
    assert lib.r6_root_gz_parse(source, len(blob) - 1,
                                ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_root_gz_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 24), (16, 21), (20, 4), (24, 1238),
                        (28, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_root_gz_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 23), (5, 0), (6, 1), (7, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_root_gz_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    print("Root gzip negatives: bad magic/header/file fields, out-of-range "
          "indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = rgz.collect(args.dump)
    check(lib, rows, rgz.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
