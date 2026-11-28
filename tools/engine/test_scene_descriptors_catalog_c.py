"""ctypes checks for the packed Scene.Lua descriptor inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import scene_descriptors_catalog as sdc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 20
FILE_SIZE = 36
STRING_BASE = HEADER_SIZE + 70 * FILE_SIZE
HEADER_FIELDS = ("version", "file_count", "string_size")
FILE_FIELDS = ("path_offset", "path_length", "root_offset", "root_length",
               "environment_offset", "environment_length", "size",
               "event_num", "event_count")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


def configure(lib):
    lib.r6_scene_descriptors_parse.restype = ctypes.c_int
    lib.r6_scene_descriptors_parse.argtypes = [BUF, ctypes.c_size_t,
                                               ctypes.POINTER(Header)]
    lib.r6_scene_descriptors_file.restype = ctypes.c_int
    lib.r6_scene_descriptors_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                              ctypes.POINTER(File)]
    lib.r6_scene_descriptors_path.restype = ctypes.c_int
    lib.r6_scene_descriptors_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                              ctypes.c_size_t]
    lib.r6_scene_descriptors_root.restype = ctypes.c_int
    lib.r6_scene_descriptors_root.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                              ctypes.c_size_t]
    lib.r6_scene_descriptors_environment.restype = ctypes.c_int
    lib.r6_scene_descriptors_environment.argtypes = [BUF, ctypes.c_size_t,
                                                     U32, BUF, ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_scene_descriptors_parse(source, len(blob),
                                          ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 70, len(blob) - STRING_BASE]

    file = File()
    text = ctypes.create_string_buffer(128)
    env = ctypes.create_string_buffer(32)
    for index, expected in enumerate(rows):
        assert lib.r6_scene_descriptors_file(source, len(blob), index,
                                             ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<9I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.root_offset,
                       file.root_length, file.environment_offset,
                       file.environment_length, file.size, file.event_num,
                       file.event_count)
        assert file.size == expected[1]
        assert (file.event_num, file.event_count) == expected[4:]
        assert lib.r6_scene_descriptors_path(source, len(blob), index,
                                             text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_scene_descriptors_root(source, len(blob), index,
                                             text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[2]
        assert lib.r6_scene_descriptors_environment(source, len(blob), index,
                                                    env, len(env)) == R6_OK
        assert env.value.decode("ascii") == expected[3]
    print("Scene descriptors: 70 paths, roots, environments and event counts "
          "match the dump")

    assert lib.r6_scene_descriptors_file(source, len(blob), 70,
                                         ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_scene_descriptors_path(source, len(blob), 70,
                                         text, len(text)) == R6_ERR_ARG
    assert lib.r6_scene_descriptors_parse(source, len(blob), None) == \
        R6_ERR_ARG
    assert lib.r6_scene_descriptors_file(source, len(blob), 0, None) == \
        R6_ERR_ARG
    assert lib.r6_scene_descriptors_root(source, len(blob), 0,
                                         None, 128) == R6_ERR_ARG
    assert lib.r6_scene_descriptors_path(source, len(blob), 0,
                                         text, 4) == R6_ERR_BUFFER
    assert lib.r6_scene_descriptors_parse(source, len(blob) - 1,
                                          ctypes.byref(header)) == \
        R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_descriptors_parse(source, len(bad),
                                          ctypes.byref(header)) == \
        R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 69), (16, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_scene_descriptors_parse(source, len(bad),
                                              ctypes.byref(header)) == \
            R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 3), (3, 10), (5, 15), (6, 0), (7, 1),
                        (8, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_scene_descriptors_parse(source, len(bad),
                                              ctypes.byref(header)) == \
            R6_ERR_FORMAT
    for slot in (8, 16):
        offset = struct.unpack_from("<I", blob, HEADER_SIZE + slot)[0]
        bad = bytearray(blob)
        bad[offset] = ord("X")
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_scene_descriptors_parse(source, len(bad),
                                              ctypes.byref(header)) == \
            R6_ERR_FORMAT
    print("Scene-descriptor negatives: bad magic/header/file/string fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = sdc.collect(args.dump)
    check(lib, rows, sdc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
