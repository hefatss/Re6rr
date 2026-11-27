"""ctypes checks for the packed stage LOADLIST inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import loadlist_catalog as lc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("block_count", U32), ("stream_count", U32),
                ("strings_size", U32), ("reserved", U32)]


class File(ctypes.Structure):
    _fields_ = [("block_first", U32), ("block_count", U32)]


class Block(ctypes.Structure):
    _fields_ = [("section", U32), ("source_size", U32),
                ("inflated_size", U32), ("wrapped", U32),
                ("stream_first", U32), ("stream_count", U32)]


class Stream(ctypes.Structure):
    _fields_ = [("offset", U32), ("size", U32)]


def configure(lib):
    lib.r6_loadlist_parse.restype = ctypes.c_int
    lib.r6_loadlist_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                      ctypes.POINTER(Header)]
    lib.r6_loadlist_file.restype = ctypes.c_int
    lib.r6_loadlist_file.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                     ctypes.POINTER(File)]
    lib.r6_loadlist_path.restype = ctypes.c_int
    lib.r6_loadlist_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                     BUF, ctypes.c_size_t]
    lib.r6_loadlist_block.restype = ctypes.c_int
    lib.r6_loadlist_block.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                      ctypes.POINTER(Block)]
    lib.r6_loadlist_bin_path.restype = ctypes.c_int
    lib.r6_loadlist_bin_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                        BUF, ctypes.c_size_t]
    lib.r6_loadlist_stream.restype = ctypes.c_int
    lib.r6_loadlist_stream.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                       ctypes.POINTER(Stream)]
    lib.r6_loadlist_stream_name.restype = ctypes.c_int
    lib.r6_loadlist_stream_name.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                            U32, BUF, ctypes.c_size_t]


def check(lib, files, blocks, streams, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_loadlist_parse(source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.block_count,
            header.stream_count, header.reserved) == (
        1, len(files), len(blocks), len(streams), 0)
    assert header.strings_size == (len(blob) - 32 - len(files) * 16 -
                                   len(blocks) * 32 - len(streams) * 16)

    file = File()
    path = ctypes.create_string_buffer(256)
    block = Block()
    bin_path = ctypes.create_string_buffer(256)
    stream = Stream()
    name = ctypes.create_string_buffer(96)
    for index, row in enumerate(files):
        assert lib.r6_loadlist_file(source, len(blob), index,
                                    ctypes.byref(file)) == R6_OK
        assert (file.block_first, file.block_count) == row[1:]
        assert lib.r6_loadlist_path(source, len(blob), index, path,
                                    len(path)) == R6_OK
        assert path.value.decode("ascii") == row[0]
    for index, row in enumerate(blocks):
        section, binpath, source_size, inflated, wrapped, first, count = row
        assert lib.r6_loadlist_block(source, len(blob), index,
                                     ctypes.byref(block)) == R6_OK
        assert (block.section, block.source_size, block.inflated_size,
                block.wrapped, block.stream_first, block.stream_count) == (
            section, source_size, inflated, wrapped, first, count)
        assert lib.r6_loadlist_bin_path(source, len(blob), index, bin_path,
                                        len(bin_path)) == R6_OK
        assert bin_path.value.decode("ascii") == binpath
    for index, row in enumerate(streams):
        assert lib.r6_loadlist_stream(source, len(blob), index,
                                      ctypes.byref(stream)) == R6_OK
        assert (stream.offset, stream.size) == row[:2]
        assert lib.r6_loadlist_stream_name(source, len(blob), index, name,
                                           len(name)) == R6_OK
        assert name.value.decode("ascii") == row[2]
    print("LOADLIST catalog: 76 files, 343 blocks and 17163 NDWD streams "
          "match the dump")

    assert lib.r6_loadlist_file(source, len(blob), len(files),
                                ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_loadlist_path(source, len(blob), len(files), path,
                                len(path)) == R6_ERR_ARG
    assert lib.r6_loadlist_block(source, len(blob), len(blocks),
                                 ctypes.byref(block)) == R6_ERR_ARG
    assert lib.r6_loadlist_bin_path(source, len(blob), len(blocks), bin_path,
                                    len(bin_path)) == R6_ERR_ARG
    assert lib.r6_loadlist_stream(source, len(blob), len(streams),
                                  ctypes.byref(stream)) == R6_ERR_ARG
    assert lib.r6_loadlist_stream_name(source, len(blob), len(streams), name,
                                       len(name)) == R6_ERR_ARG
    assert lib.r6_loadlist_path(source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_loadlist_stream_name(source, len(blob), 0, name,
                                       4) == R6_ERR_BUFFER
    assert lib.r6_loadlist_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_loadlist_stream(source, len(blob), 0,
                                  None) == R6_ERR_ARG
    assert lib.r6_loadlist_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_loadlist_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_loadlist_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 75), (16, 342), (20, 17162),
                        (24, 1), (28, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_loadlist_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 343), (12, 343)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, 32 + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_loadlist_file(source, len(bad), 0,
                                    ctypes.byref(file)) == R6_ERR_FORMAT
    base = 32 + len(files) * 16
    for slot, value in ((20, 2), (24, 17163), (28, 17163)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, base + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_loadlist_block(source, len(bad), 0,
                                     ctypes.byref(block)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 32, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_loadlist_path(source, len(bad), 0, path,
                                len(path)) == R6_ERR_FORMAT
    stream_base = base + len(blocks) * 32
    bad = bytearray(blob)
    struct.pack_into("<I", bad, stream_base, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_loadlist_stream(source, len(bad), 0,
                                  ctypes.byref(stream)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, stream_base + 4, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_loadlist_stream(source, len(bad), 0,
                                  ctypes.byref(stream)) == R6_ERR_FORMAT
    print("LOADLIST negatives: bad magic/counts/ranges, truncation, bad "
          "paths/streams, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, blocks, streams = lc.collect(args.dump)
    check(lib, files, blocks, streams, lc.build(files, blocks, streams))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
