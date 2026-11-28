"""ctypes checks for the packed root INI inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import root_ini_catalog as ri  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
FILE_SIZE = 40
KEY_SIZE = 16
KEY_BASE = HEADER_SIZE + 2 * FILE_SIZE
COMMENT_BASE = KEY_BASE + 41 * KEY_SIZE
STRING_BASE = COMMENT_BASE + 3 * 8
HEADER_FIELDS = ("version", "file_count", "key_count", "string_size",
                 "source_bytes", "comment_count")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines",
               "section_offset", "section_length", "key_base", "keys",
               "comment_base", "comments")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Key(ctypes.Structure):
    _fields_ = [("key_offset", U32), ("key_length", U32),
                ("value_offset", U32), ("value_length", U32)]


def configure(lib):
    for name, args in (
        ("r6_root_ini_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_root_ini_file", [BUF, ctypes.c_size_t, U32,
                              ctypes.POINTER(File)]),
        ("r6_root_ini_path", [BUF, ctypes.c_size_t, U32, BUF,
                              ctypes.c_size_t]),
        ("r6_root_ini_section", [BUF, ctypes.c_size_t, U32, BUF,
                                 ctypes.c_size_t]),
        ("r6_root_ini_key", [BUF, ctypes.c_size_t, U32, BUF,
                             ctypes.c_size_t]),
        ("r6_root_ini_value", [BUF, ctypes.c_size_t, U32, BUF,
                               ctypes.c_size_t]),
        ("r6_root_ini_comment", [BUF, ctypes.c_size_t, U32, BUF,
                                 ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_root_ini_parse(source, len(blob),
                                 ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 2, 41, len(blob) - STRING_BASE, 1039, 3]
    file = File()
    text = ctypes.create_string_buffer(128)
    keys = []
    comments = []
    for index, expected in enumerate(files):
        assert lib.r6_root_ini_file(source, len(blob), index,
                                    ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<10I", blob,
                                 HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.size,
                       file.lines, file.section_offset, file.section_length,
                       file.key_base, file.keys, file.comment_base,
                       file.comments)
        assert (file.size, file.lines, file.keys, file.comments) == \
            (expected[1], expected[2], len(expected[4]), len(expected[5]))
        assert lib.r6_root_ini_path(source, len(blob), index,
                                    text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_root_ini_section(source, len(blob), index,
                                       text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[3]
        keys.extend(expected[4])
        comments.extend(expected[5])
    for index, expected in enumerate(keys):
        assert lib.r6_root_ini_key(source, len(blob), index,
                                   text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_root_ini_value(source, len(blob), index,
                                     text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[1]
    for index, expected in enumerate(comments):
        assert lib.r6_root_ini_comment(source, len(blob), index,
                                       text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
    print("Root INI: 2 files, 41 keys, 41 values and 3 comments match the dump")

    assert lib.r6_root_ini_file(source, len(blob), 2,
                                ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_root_ini_key(source, len(blob), 41,
                               text, len(text)) == R6_ERR_ARG
    assert lib.r6_root_ini_comment(source, len(blob), 3,
                                   text, len(text)) == R6_ERR_ARG
    assert lib.r6_root_ini_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_root_ini_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_root_ini_key(source, len(blob), 0,
                               text, 4) == R6_ERR_BUFFER
    assert lib.r6_root_ini_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_root_ini_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1), (16, 40), (20, 0), (24, 1038),
                        (28, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_root_ini_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 0), (5, 2), (6, 1), (7, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_root_ini_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    print("Root-INI negatives: bad magic/header/file/key/comment fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = ri.collect(args.dump)
    check(lib, files, ri.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
