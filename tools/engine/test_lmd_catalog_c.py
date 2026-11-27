"""ctypes checks for the packed .LMD gzip/XMD header reader."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import lmd_catalog as lc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
HEADER_SIZE = 24
FILE_OFF = HEADER_SIZE
STREAM_OFF = FILE_OFF + lc.FILES * lc.FILE.size
STRINGS_OFF = STREAM_OFF + lc.FILES * lc.STREAMS_PER_FILE * lc.STREAM.size


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in
                ("version", "file_count", "stream_count", "strings_size")]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "compressed_size", "gzip_flags", "gzip_mtime", "gzip_xfl_os",
        "expected_size", "inflated_size", "xmd_version", "stream_first")]


def configure(lib):
    lib.r6_lmd_parse.restype = ctypes.c_int
    lib.r6_lmd_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                 ctypes.POINTER(Header)]
    lib.r6_lmd_file.restype = ctypes.c_int
    lib.r6_lmd_file.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                ctypes.POINTER(File)]
    lib.r6_lmd_path.restype = ctypes.c_int
    lib.r6_lmd_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                BUF, ctypes.c_size_t]
    lib.r6_lmd_stream.restype = ctypes.c_int
    lib.r6_lmd_stream.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32, U32,
                                  PU32, PU32]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_lmd_parse(source, len(blob),
                            ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.stream_count,
            header.strings_size) == (1, lc.FILES, 3,
                                     len(blob) - STRINGS_OFF)

    file = File()
    path = ctypes.create_string_buffer(256)
    offset = U32()
    stream_size = U32()
    for index, row in enumerate(rows):
        (want_path, compressed, flags, mtime, xfl_os, expected, inflated,
         version, offsets, sizes) = row
        assert lib.r6_lmd_file(source, len(blob), index,
                               ctypes.byref(file)) == R6_OK
        assert (file.compressed_size, file.gzip_flags, file.gzip_mtime,
                file.gzip_xfl_os, file.expected_size, file.inflated_size,
                file.xmd_version, file.stream_first) == (
            compressed, flags, mtime, xfl_os, expected, inflated, version,
            index * 3)
        assert lib.r6_lmd_path(source, len(blob), index, path,
                               len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
        for local in range(3):
            assert lib.r6_lmd_stream(source, len(blob), index, local,
                                     ctypes.byref(offset),
                                     ctypes.byref(stream_size)) == R6_OK
            assert (offset.value, stream_size.value) == (
                offsets[local], sizes[local])
    print("LMD catalog: %d gzip/XMD.001 paths, header facts and three stream "
          "sizes each match the dump" % len(rows))

    assert lib.r6_lmd_file(source, len(blob), lc.FILES,
                           ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_lmd_path(source, len(blob), lc.FILES, path,
                           len(path)) == R6_ERR_ARG
    assert lib.r6_lmd_stream(source, len(blob), 0, 3,
                             ctypes.byref(offset),
                             ctypes.byref(stream_size)) == R6_ERR_ARG
    assert lib.r6_lmd_stream(source, len(blob), 0, 0, None,
                             ctypes.byref(stream_size)) == R6_OK
    assert lib.r6_lmd_path(source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_lmd_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_lmd_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lmd_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    for offset_at, value in ((8, 2), (12, 984), (16, 4)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, offset_at, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_lmd_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for field_at, value in ((8, 0), (24, 1), (28, 47), (32, 2), (36, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_OFF + field_at, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_lmd_file(source, len(bad), 0,
                               ctypes.byref(file)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, FILE_OFF, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lmd_path(source, len(bad), 0, path,
                           len(path)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, STREAM_OFF + 4, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lmd_stream(source, len(bad), 0, 0,
                             ctypes.byref(offset),
                             ctypes.byref(stream_size)) == R6_ERR_FORMAT
    print("LMD negatives: bad magic/version/counts/ISIZE/XMD, bad path and "
          "stream size, truncation, bad index/null output and short buffer "
          "rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = lc.collect(args.dump)
    check(lib, rows, lc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
