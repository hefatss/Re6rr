"""ctypes checks for the packed .TEX/.MDL XMD.001 inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import xmd_asset_catalog as xac  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("stream_count", U32), ("strings_size", U32)]


class File(ctypes.Structure):
    _fields_ = [("source_size", U32), ("inflated_size", U32),
                ("ext", U32), ("wrap", U32), ("gzip_flags", U32),
                ("gzip_mtime", U32), ("gzip_xfl_os", U32),
                ("expected_size", U32), ("xmd_version", U32),
                ("stream_first", U32), ("stream_count", U32)]


def configure(lib):
    lib.r6_xmd_asset_parse.restype = ctypes.c_int
    lib.r6_xmd_asset_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_xmd_asset_file.restype = ctypes.c_int
    lib.r6_xmd_asset_file.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                      ctypes.POINTER(File)]
    lib.r6_xmd_asset_path.restype = ctypes.c_int
    lib.r6_xmd_asset_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                      BUF, ctypes.c_size_t]
    lib.r6_xmd_asset_stream.restype = ctypes.c_int
    lib.r6_xmd_asset_stream.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                        U32, PU32, PU32]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_xmd_asset_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    total = sum(len(row[10]) for row in rows)
    assert (header.version, header.file_count, header.stream_count,
            header.strings_size) == (
        1, len(rows), total,
        len(blob) - 24 - len(rows) * 52 - total * 8)

    file = File()
    path = ctypes.create_string_buffer(256)
    offset = U32()
    size = U32()
    exts = {}
    wraps = {}
    first = 0
    for index, row in enumerate(rows):
        want_path, ext, wrap, source_size, inflated, flags, mtime, xfl, \
            expected, version, offsets, sizes = row
        assert lib.r6_xmd_asset_file(
            source, len(blob), index, ctypes.byref(file)) == R6_OK
        assert (file.source_size, file.inflated_size, file.ext, file.wrap,
                file.gzip_flags, file.gzip_mtime, file.gzip_xfl_os,
                file.expected_size, file.xmd_version, file.stream_first,
                file.stream_count) == (
            source_size, inflated, ext, wrap, flags, mtime, xfl, expected,
            version, first, len(offsets))
        assert lib.r6_xmd_asset_path(
            source, len(blob), index, path, len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
        for local, (want_offset, want_size) in enumerate(zip(offsets, sizes)):
            assert lib.r6_xmd_asset_stream(
                source, len(blob), index, local, ctypes.byref(offset),
                ctypes.byref(size)) == R6_OK
            assert (offset.value, size.value) == (want_offset, want_size)
        exts[ext] = exts.get(ext, 0) + 1
        wraps[wrap] = wraps.get(wrap, 0) + 1
        first += len(offsets)
    assert exts == {0: 1250, 1: 610}
    assert wraps == {0: 8, 1: 1852}
    print("XMD assets: 1860 .TEX/.MDL paths, headers and 28863 streams "
          "match the dump")

    assert lib.r6_xmd_asset_file(
        source, len(blob), len(rows), ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_xmd_asset_path(
        source, len(blob), len(rows), path, len(path)) == R6_ERR_ARG
    assert lib.r6_xmd_asset_stream(
        source, len(blob), 0, len(rows[0][10]), ctypes.byref(offset),
        ctypes.byref(size)) == R6_ERR_ARG
    assert lib.r6_xmd_asset_path(source, len(blob), 0, path,
                                 4) == R6_ERR_BUFFER
    assert lib.r6_xmd_asset_stream(
        source, len(blob), 0, 0, None, ctypes.byref(size)) == R6_ERR_ARG
    assert lib.r6_xmd_asset_file(source, len(blob), 0,
                                 None) == R6_ERR_ARG
    assert lib.r6_xmd_asset_parse(source, len(blob),
                                  None) == R6_ERR_ARG
    assert lib.r6_xmd_asset_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmd_asset_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1859), (16, 28862), (20, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmd_asset_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 0), (20, 0xffffffff),
                        (40, 1), (44, 28863), (48, 28863)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, 24 + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmd_asset_file(
            source, len(bad), 0, ctypes.byref(file)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24 + 36, rows[0][4] + 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmd_asset_file(
        source, len(bad), 0, ctypes.byref(file)) == R6_ERR_FORMAT
    raw_index = next(i for i, row in enumerate(rows) if row[2] == 0)
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24 + raw_index * 52 + 24, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmd_asset_file(
        source, len(bad), raw_index, ctypes.byref(file)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmd_asset_path(source, len(bad), 0, path,
                                 len(path)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    stream_row = 24 + len(rows) * 52
    struct.pack_into("<I", bad, stream_row, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmd_asset_stream(
        source, len(bad), 0, 0, ctypes.byref(offset),
        ctypes.byref(size)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, stream_row + 4, rows[0][11][0] + 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmd_asset_stream(
        source, len(bad), 0, 0, ctypes.byref(offset),
        ctypes.byref(size)) == R6_ERR_FORMAT
    print("XMD negatives: bad magic/counts/wrap/version/ranges, truncation, "
          "bad path/streams, null outputs and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = xac.collect(args.dump)
    check(lib, rows, xac.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
