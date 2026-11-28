"""ctypes checks for the packed root setting.lua.gz inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import setting_lua_gz_catalog as slg  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 36
FILE_SIZE = 24
SPAN_SIZE = 8
KEY_BASE = HEADER_SIZE + 6 * FILE_SIZE
VALUE_BASE = KEY_BASE + 53 * SPAN_SIZE
STRING_BASE = VALUE_BASE + 6 * 53 * SPAN_SIZE
HEADER_FIELDS = ("version", "file_count", "key_count", "string_size",
                 "source_bytes", "inflated_bytes", "line_count")
FILE_FIELDS = ("path_offset", "path_length", "compressed_size", "mtime",
               "crc32", "inflated_size")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


def configure(lib):
    lib.r6_setting_lua_gz_parse.restype = ctypes.c_int
    lib.r6_setting_lua_gz_parse.argtypes = [BUF, ctypes.c_size_t,
                                            ctypes.POINTER(Header)]
    lib.r6_setting_lua_gz_file.restype = ctypes.c_int
    lib.r6_setting_lua_gz_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                           ctypes.POINTER(File)]
    lib.r6_setting_lua_gz_path.restype = ctypes.c_int
    lib.r6_setting_lua_gz_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                           ctypes.c_size_t]
    lib.r6_setting_lua_gz_key.restype = ctypes.c_int
    lib.r6_setting_lua_gz_key.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                          ctypes.c_size_t]
    lib.r6_setting_lua_gz_value.restype = ctypes.c_int
    lib.r6_setting_lua_gz_value.argtypes = [BUF, ctypes.c_size_t, U32, U32,
                                            BUF, ctypes.c_size_t]


def check(lib, keys, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_setting_lua_gz_parse(source, len(blob),
                                       ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 6, 53, len(blob) - STRING_BASE, 2882, 7258, 60]

    file = File()
    text = ctypes.create_string_buffer(96)
    for index, expected in enumerate(files):
        assert lib.r6_setting_lua_gz_file(source, len(blob), index,
                                          ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<6I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length,
                       file.compressed_size, file.mtime, file.crc32,
                       file.inflated_size)
        assert (file.compressed_size, file.mtime, file.crc32,
                file.inflated_size) == expected[1:5]
        assert lib.r6_setting_lua_gz_path(source, len(blob), index,
                                          text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    for index, expected in enumerate(keys):
        assert lib.r6_setting_lua_gz_key(source, len(blob), index,
                                         text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
        offset, length = struct.unpack_from("<2I", blob,
                                             KEY_BASE + index * SPAN_SIZE)
        assert blob[offset:offset + length].decode("ascii") == expected
    for file_index, expected in enumerate(files):
        for key_index, expected_value in enumerate(expected[5]):
            assert lib.r6_setting_lua_gz_value(
                source, len(blob), file_index, key_index,
                text, len(text)) == R6_OK
            assert text.value.decode("ascii") == expected_value
            at = VALUE_BASE + (file_index * 53 + key_index) * SPAN_SIZE
            offset, length = struct.unpack_from("<2I", blob, at)
            assert blob[offset:offset + length].decode("ascii") == \
                expected_value
    print("Setting.lua.gz: 6 gzip envelopes, 53 keys and 318 integer rows "
          "match the dump")

    assert lib.r6_setting_lua_gz_file(source, len(blob), 6,
                                      ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_setting_lua_gz_path(source, len(blob), 6,
                                      text, len(text)) == R6_ERR_ARG
    assert lib.r6_setting_lua_gz_key(source, len(blob), 53,
                                     text, len(text)) == R6_ERR_ARG
    assert lib.r6_setting_lua_gz_value(source, len(blob), 6, 0,
                                       text, len(text)) == R6_ERR_ARG
    assert lib.r6_setting_lua_gz_value(source, len(blob), 0, 53,
                                       text, len(text)) == R6_ERR_ARG
    assert lib.r6_setting_lua_gz_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_setting_lua_gz_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_setting_lua_gz_key(source, len(blob), 0,
                                     text, 4) == R6_ERR_BUFFER
    assert lib.r6_setting_lua_gz_value(source, len(blob), 0, 0,
                                       text, 4) == R6_ERR_BUFFER
    assert lib.r6_setting_lua_gz_parse(source, len(blob) - 1,
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_setting_lua_gz_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 5), (16, 52), (20, 0), (24, 2881),
                        (28, 7257), (32, 59)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_setting_lua_gz_parse(source, len(bad),
                                           ctypes.byref(header)) == \
            R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 2), (2, 17), (5, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_setting_lua_gz_parse(source, len(bad),
                                           ctypes.byref(header)) == \
            R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, KEY_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_setting_lua_gz_parse(source, len(bad),
                                           ctypes.byref(header)) == \
            R6_ERR_FORMAT
    at = VALUE_BASE
    offset, length = struct.unpack_from("<2I", blob, at)
    bad = bytearray(blob)
    bad[offset] = ord("x")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_setting_lua_gz_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    print("Setting.lua.gz negatives: bad magic/header/file/key/value fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    keys, files = slg.collect(args.dump)
    expected = []
    for path, size, mtime, crc, inflated_size, rows in files:
        expected.append((path, size, mtime, crc, inflated_size,
                         [value for _, value in rows]))
    check(lib, keys, expected, slg.build(keys, files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
