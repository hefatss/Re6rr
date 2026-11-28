"""ctypes checks for the packed story-rival block inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import rival_block_catalog as rvb  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 36
BLOCK_SIZE = 76
BLOCK_BASE = HEADER_SIZE + BLOCK_SIZE
STRING_BASE = HEADER_SIZE + 399 * BLOCK_SIZE
HEADER_FIELDS = ("version", "file_count", "block_count", "unique_count",
                 "string_size", "source_bytes", "lines")
KEYWORDS = ("Band", "Feature", "StartConfig", "EventFirst", "EventLast")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Block(ctypes.Structure):
    _fields_ = [("name_offset", U32), ("name_length", U32),
                ("line_start", U32), ("line_count", U32),
                ("row_offset", U32 * 5), ("row_length", U32 * 5),
                ("count", U32 * 5)]


def configure(lib):
    for name, args in (
        ("r6_rival_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_rival_path", [BUF, ctypes.c_size_t, BUF, ctypes.c_size_t]),
        ("r6_rival_block", [BUF, ctypes.c_size_t, U32,
                            ctypes.POINTER(Block)]),
        ("r6_rival_name", [BUF, ctypes.c_size_t, U32, BUF,
                           ctypes.c_size_t]),
        ("r6_rival_keyword", [BUF, ctypes.c_size_t, U32, U32, BUF,
                              ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_rival_parse(source, len(blob),
                              ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 398, 201, len(blob) - STRING_BASE, 145966, 5261]
    text = ctypes.create_string_buffer(96)
    assert lib.r6_rival_path(source, len(blob),
                             text, len(text)) == R6_OK
    assert text.value.decode("ascii") == entry[0]

    block = Block()
    for index, expected in enumerate(entry[3]):
        assert lib.r6_rival_block(source, len(blob), index,
                                  ctypes.byref(block)) == R6_OK
        raw = struct.unpack_from("<19I", blob, BLOCK_BASE + index * BLOCK_SIZE)
        fields = [block.name_offset, block.name_length, block.line_start,
                  block.line_count]
        fields.extend(block.row_offset)
        fields.extend(block.row_length)
        fields.extend(block.count)
        assert raw == tuple(fields)
        assert (block.line_start, block.line_count) == (expected[1],
                                                        expected[2])
        assert lib.r6_rival_name(source, len(blob), index,
                                 text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        for keyword, value in enumerate(expected[3]):
            assert lib.r6_rival_keyword(source, len(blob), index, keyword,
                                        text, len(text)) == R6_OK
            assert text.value.decode("ascii") == value
        assert tuple(block.count) == expected[4]
    print("Rival: 398 blocks, 201 unique names, 1,990 keyword rows match")

    assert lib.r6_rival_block(source, len(blob), 398,
                              ctypes.byref(block)) == R6_ERR_ARG
    assert lib.r6_rival_name(source, len(blob), 398,
                             text, len(text)) == R6_ERR_ARG
    assert lib.r6_rival_keyword(source, len(blob), 0, 5,
                                text, len(text)) == R6_ERR_ARG
    assert lib.r6_rival_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_rival_block(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_rival_path(source, len(blob), text, 4) == R6_ERR_BUFFER
    assert lib.r6_rival_parse(source, len(blob) - 1,
                              ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_rival_parse(source, len(bad),
                              ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 397), (20, 200), (24, 0),
                        (28, 145965), (32, 5260)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_rival_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 5261), (3, 0), (12, 2), (14, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, BLOCK_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_rival_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    print("Rival negatives: bad magic/header/block fields, out-of-range "
          "indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = rvb.collect(args.dump)
    check(lib, entry, rvb.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
