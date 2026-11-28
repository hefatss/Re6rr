"""ctypes checks for the packed XMD version 0/1 stream directory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import xmd_v1_directory_catalog as xd1  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
FILE_SIZE = 28
STREAM_SIZE = 16
STREAM_BASE = HEADER_SIZE + 3 * FILE_SIZE
STRING_BASE = STREAM_BASE + 30 * STREAM_SIZE
HEADER_FIELDS = ("version", "file_count", "stream_count", "string_size",
                 "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "size", "version", "table_end",
               "stream_index", "count")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Stream(ctypes.Structure):
    _fields_ = [("offset", U32), ("length", U32),
                ("magic", ctypes.c_ubyte * 8)]


def configure(lib):
    for name, args in (
        ("r6_xmd_v1_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_xmd_v1_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_xmd_v1_path", [BUF, ctypes.c_size_t, U32, BUF,
                            ctypes.c_size_t]),
        ("r6_xmd_v1_stream", [BUF, ctypes.c_size_t, U32,
                              ctypes.POINTER(Stream)])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_xmd_v1_parse(source, len(blob),
                               ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 3, 30, len(blob) - STRING_BASE, 527072]

    file = File()
    text = ctypes.create_string_buffer(96)
    streams = []
    for index, expected in enumerate(files):
        assert lib.r6_xmd_v1_file(source, len(blob), index,
                                  ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<7I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.size,
                       file.version, file.table_end, file.stream_index,
                       file.count)
        assert (file.size, file.version, file.count) == \
            (expected[1], expected[2], len(expected[5]))
        assert lib.r6_xmd_v1_path(source, len(blob), index,
                                  text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        streams.extend(expected[5])
    assert len(streams) == 30
    stream = Stream()
    for index, expected in enumerate(streams):
        assert lib.r6_xmd_v1_stream(source, len(blob), index,
                                    ctypes.byref(stream)) == R6_OK
        raw = struct.unpack_from("<2I8s", blob,
                                 STREAM_BASE + index * STREAM_SIZE)
        expected_magic = expected[2].ljust(8, b"\0")
        assert raw[:2] == (stream.offset, stream.length)
        assert bytes(raw[2]) == expected_magic
        assert bytes(stream.magic) == expected_magic
    print("XMD v0/1: 3 containers, 30 stream offsets and magic words match")

    assert lib.r6_xmd_v1_file(source, len(blob), 3,
                              ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_xmd_v1_stream(source, len(blob), 30,
                                ctypes.byref(stream)) == R6_ERR_ARG
    assert lib.r6_xmd_v1_path(source, len(blob), 3,
                              text, len(text)) == R6_ERR_ARG
    assert lib.r6_xmd_v1_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_xmd_v1_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_xmd_v1_stream(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_xmd_v1_path(source, len(blob), 0,
                              text, 4) == R6_ERR_BUFFER
    assert lib.r6_xmd_v1_parse(source, len(blob) - 1,
                               ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmd_v1_parse(source, len(bad),
                               ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 29), (20, 0), (24, 527071)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmd_v1_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 0), (3, 2), (4, 8), (5, 1), (6, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmd_v1_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 527072)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, STREAM_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmd_v1_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    print("XMD-v1 negatives: bad magic/header/file/stream fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = xd1.collect(args.dump)
    check(lib, files, xd1.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
