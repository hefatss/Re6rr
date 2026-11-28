"""ctypes checks for the packed scene function inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import scene_func_catalog as sfn  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
FILE_SIZE = 24
FUNC_SIZE = 16
STRING_BASE = HEADER_SIZE + 3 * FILE_SIZE + 43 * FUNC_SIZE
HEADER_FIELDS = ("version", "file_count", "function_count", "string_size",
                 "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines",
               "function_base", "count")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Func(ctypes.Structure):
    _fields_ = [("name_offset", U32), ("name_length", U32),
                ("result_offset", U32), ("result_length", U32)]


def configure(lib):
    for name, args in (
        ("r6_scene_func_parse", [BUF, ctypes.c_size_t,
                                 ctypes.POINTER(Header)]),
        ("r6_scene_func_file", [BUF, ctypes.c_size_t, U32,
                                ctypes.POINTER(File)]),
        ("r6_scene_func_path", [BUF, ctypes.c_size_t, U32, BUF,
                                ctypes.c_size_t]),
        ("r6_scene_func_row", [BUF, ctypes.c_size_t, U32,
                               ctypes.POINTER(Func)]),
        ("r6_scene_func_name", [BUF, ctypes.c_size_t, U32, BUF,
                                ctypes.c_size_t]),
        ("r6_scene_func_result", [BUF, ctypes.c_size_t, U32, BUF,
                                  ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_scene_func_parse(source, len(blob),
                                   ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 3, 43, len(blob) - STRING_BASE, 4289]

    file = File()
    text = ctypes.create_string_buffer(128)
    functions = []
    for index, expected in enumerate(files):
        assert lib.r6_scene_func_file(source, len(blob), index,
                                      ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<6I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.size,
                       file.lines, file.function_base, file.count)
        assert (file.size, file.lines, file.count) == \
            (expected[1], expected[2], len(expected[3]))
        assert lib.r6_scene_func_path(source, len(blob), index,
                                      text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        functions.extend(expected[3])
    assert len(functions) == 43
    func = Func()
    for index, expected in enumerate(functions):
        assert lib.r6_scene_func_row(source, len(blob), index,
                                     ctypes.byref(func)) == R6_OK
        raw = struct.unpack_from("<4I", blob,
                                 STRING_BASE - 43 * FUNC_SIZE + index * 16)
        assert raw == (func.name_offset, func.name_length,
                       func.result_offset, func.result_length)
        assert lib.r6_scene_func_name(source, len(blob), index,
                                      text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_scene_func_result(source, len(blob), index,
                                        text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[1]
    print("Scene func: 3 files, 43 names and return expressions match")

    assert lib.r6_scene_func_file(source, len(blob), 3,
                                  ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_scene_func_row(source, len(blob), 43,
                                 ctypes.byref(func)) == R6_ERR_ARG
    assert lib.r6_scene_func_path(source, len(blob), 3,
                                  text, len(text)) == R6_ERR_ARG
    assert lib.r6_scene_func_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_scene_func_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_scene_func_path(source, len(blob), 0,
                                  text, 4) == R6_ERR_BUFFER
    assert lib.r6_scene_func_parse(source, len(blob) - 1,
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_func_parse(source, len(bad),
                                   ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 42), (20, 0), (24, 4288)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_scene_func_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 0), (4, 7), (5, 9)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_scene_func_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    print("Scene-func negatives: bad magic/header/file/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = sfn.collect(args.dump)
    check(lib, files, sfn.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
