"""ctypes checks for the packed Enma trail header inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import trail_header_catalog as th  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 44
FILE_SIZE = 40
NAME_SIZE = 12
FILE_BASE = HEADER_SIZE
NAME_BASE = FILE_BASE + 2 * FILE_SIZE
STRING_BASE = NAME_BASE + 8 * NAME_SIZE
HEADER_FIELDS = ("version", "file_count", "name_count", "source_bytes",
                 "record_count", "record_size", "string_size",
                 "marker_word", "reserved")
FILE_FIELDS = ("name_offset", "name_length", "size", "links", "name_base",
               "name_count", "marker_offset", "marker_word", "record_count",
               "trailer")
NAME_FIELDS = ("name_offset", "name_length", "source_offset")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Name(ctypes.Structure):
    _fields_ = [(name, U32) for name in NAME_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_th_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_th_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_th_path", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_th_name", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Name)]),
        ("r6_th_name_text", [BUF, ctypes.c_size_t, U32, BUF,
                             ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, names, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_th_parse(source, len(blob),
                           ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 2, 8, 207664, 3991, 52, len(blob) - STRING_BASE, 3, 0]
    text = ctypes.create_string_buffer(96)
    file = File()
    for index, expected in enumerate(files):
        assert lib.r6_th_file(source, len(blob), index,
                              ctypes.byref(file)) == R6_OK
        packed = struct.unpack_from("<10I", blob, FILE_BASE + index * FILE_SIZE)
        assert packed == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.links, file.name_base, file.name_count,
                file.record_count, file.trailer) == (
                    expected[1], expected[2], sum(
                        prior[3] for prior in files[:index]), expected[3],
                    expected[5], expected[6])
        assert lib.r6_th_path(source, len(blob), index,
                              text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    name = Name()
    for index, expected in enumerate(names):
        assert lib.r6_th_name(source, len(blob), index,
                              ctypes.byref(name)) == R6_OK
        packed = struct.unpack_from("<3I", blob, NAME_BASE + index * NAME_SIZE)
        assert packed == tuple(getattr(name, field) for field in NAME_FIELDS)
        assert name.source_offset == expected[1]
        assert lib.r6_th_name_text(source, len(blob), index,
                                   text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    print("Enma trails: 2 files, 8 link names and 3991 record headers match")

    assert lib.r6_th_file(source, len(blob), 2, ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_th_path(source, len(blob), 2, text, len(text)) == R6_ERR_ARG
    assert lib.r6_th_name(source, len(blob), 8, ctypes.byref(name)) == R6_ERR_ARG
    assert lib.r6_th_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_th_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_th_path(source, len(blob), 0, text, 4) == R6_ERR_BUFFER
    assert lib.r6_th_parse(source, len(blob) - 1,
                           ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_th_parse(source, len(bad),
                           ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1), (16, 7), (20, 207663), (24, 3990),
                        (28, 51), (32, 0), (36, 2), (40, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_th_parse(source, len(bad),
                               ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 34413), (3, 2), (4, 1), (5, 5), (6, 25),
                        (7, 4), (8, 660), (9, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_th_parse(source, len(bad),
                               ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 7)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, NAME_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_th_parse(source, len(bad),
                               ctypes.byref(header)) == R6_ERR_FORMAT
    print("Enma trail negatives: bad magic/header/file/name fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, names = th.collect(args.dump)
    check(lib, files, names, th.build(files, names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
