"""ctypes checks for the packed story-series token inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_series_tokens_catalog as sst  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
BLOCK_SIZE = 12
SPAN_SIZE = 8
LINE_BASE = HEADER_SIZE + 125 * BLOCK_SIZE
STRING_BASE = LINE_BASE + 1249 * SPAN_SIZE
HEADER_FIELDS = ("version", "block_count", "line_count", "string_size",
                 "source_size", "source_lines")
BLOCK_FIELDS = ("header_offset", "header_length", "lines")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Block(ctypes.Structure):
    _fields_ = [(name, U32) for name in BLOCK_FIELDS]


def configure(lib):
    lib.r6_story_series_parse.restype = ctypes.c_int
    lib.r6_story_series_parse.argtypes = [BUF, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_story_series_block.restype = ctypes.c_int
    lib.r6_story_series_block.argtypes = [BUF, ctypes.c_size_t, U32,
                                          ctypes.POINTER(Block)]
    lib.r6_story_series_header.restype = ctypes.c_int
    lib.r6_story_series_header.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                           ctypes.c_size_t]
    lib.r6_story_series_line.restype = ctypes.c_int
    lib.r6_story_series_line.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                         ctypes.c_size_t]


def check(lib, blocks, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_story_series_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 125, 1249, len(blob) - STRING_BASE, 28433, 1511]

    block = Block()
    text = ctypes.create_string_buffer(96)
    lines = []
    for index, (expected_header, group) in enumerate(blocks):
        assert lib.r6_story_series_block(source, len(blob), index,
                                         ctypes.byref(block)) == R6_OK
        raw = struct.unpack_from("<3I", blob, HEADER_SIZE + index * BLOCK_SIZE)
        assert raw == (block.header_offset, block.header_length, block.lines)
        assert block.lines == len(group)
        assert lib.r6_story_series_header(source, len(blob), index,
                                          text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected_header
        lines.extend(group)
    for index, expected in enumerate(lines):
        assert lib.r6_story_series_line(source, len(blob), index,
                                        text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
        offset, length = struct.unpack_from(
            "<2I", blob, LINE_BASE + index * SPAN_SIZE)
        assert blob[offset:offset + length].decode("ascii") == expected
    print("Story series: 125 block headers and 1249 token lines match the "
          "dump")

    assert lib.r6_story_series_block(source, len(blob), 125,
                                     ctypes.byref(block)) == R6_ERR_ARG
    assert lib.r6_story_series_header(source, len(blob), 125,
                                      text, len(text)) == R6_ERR_ARG
    assert lib.r6_story_series_line(source, len(blob), 1249,
                                    text, len(text)) == R6_ERR_ARG
    assert lib.r6_story_series_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_story_series_block(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_story_series_line(source, len(blob), 0,
                                    text, 4) == R6_ERR_BUFFER
    assert lib.r6_story_series_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_story_series_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 124), (16, 1248), (20, 0), (24, 28432),
                        (28, 1510)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_story_series_parse(source, len(bad),
                                         ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 7), (2, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_story_series_parse(source, len(bad),
                                         ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (1, 200)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, LINE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_story_series_parse(source, len(bad),
                                         ctypes.byref(header)) == R6_ERR_FORMAT
    print("Story-series negatives: bad magic/header/block/line fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    blocks = sst.collect(args.dump)
    check(lib, blocks, sst.build(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
