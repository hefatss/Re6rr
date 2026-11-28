"""ctypes checks for the packed Lua accessor inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import accessor_script_catalog as acc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
FILE_SIZE = 28
FUNC_SIZE = 28
FUNC_BASE = HEADER_SIZE + 7 * FILE_SIZE
STRING_BASE = FUNC_BASE + 155 * FUNC_SIZE
HEADER_FIELDS = ("version", "file_count", "function_count", "string_size",
                 "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines",
               "function_base", "count", "returns")
FUNC_FIELDS = ("name_offset", "name_length", "args_offset", "args_length",
               "result_offset", "result_length", "line")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Func(ctypes.Structure):
    _fields_ = [(name, U32) for name in FUNC_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_accessor_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_accessor_file", [BUF, ctypes.c_size_t, U32,
                              ctypes.POINTER(File)]),
        ("r6_accessor_path", [BUF, ctypes.c_size_t, U32, BUF,
                              ctypes.c_size_t]),
        ("r6_accessor_func", [BUF, ctypes.c_size_t, U32,
                              ctypes.POINTER(Func)]),
        ("r6_accessor_name", [BUF, ctypes.c_size_t, U32, BUF,
                              ctypes.c_size_t]),
        ("r6_accessor_args", [BUF, ctypes.c_size_t, U32, BUF,
                              ctypes.c_size_t]),
        ("r6_accessor_result", [BUF, ctypes.c_size_t, U32, BUF,
                                ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, functions, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_accessor_parse(source, len(blob),
                                 ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 7, 155, len(blob) - STRING_BASE, 35256]
    text = ctypes.create_string_buffer(160)
    file = File()
    for index, expected in enumerate(files):
        assert lib.r6_accessor_file(source, len(blob), index,
                                    ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<7I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.lines, file.function_base, file.count,
                file.returns) == (expected[1], expected[2], expected[3],
                                  expected[4], expected[5])
        assert lib.r6_accessor_path(source, len(blob), index,
                                    text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    func = Func()
    for index, expected in enumerate(functions):
        assert lib.r6_accessor_func(source, len(blob), index,
                                    ctypes.byref(func)) == R6_OK
        raw = struct.unpack_from("<7I", blob, FUNC_BASE + index * FUNC_SIZE)
        assert raw == tuple(getattr(func, name) for name in FUNC_FIELDS)
        assert func.line == expected[3]
        for name, want in (("name", expected[0]), ("args", expected[1]),
                           ("result", expected[2])):
            assert getattr(lib, "r6_accessor_" + name)(
                source, len(blob), index, text, len(text)) == R6_OK
            assert text.value.decode("ascii") == want
    print("Accessor: 7 scripts, 155 functions, names, args and returns match")

    assert lib.r6_accessor_file(source, len(blob), 7,
                                ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_accessor_path(source, len(blob), 7,
                                text, len(text)) == R6_ERR_ARG
    assert lib.r6_accessor_func(source, len(blob), 155,
                                ctypes.byref(func)) == R6_ERR_ARG
    assert lib.r6_accessor_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_accessor_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_accessor_func(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_accessor_path(source, len(blob), 0,
                                text, 4) == R6_ERR_BUFFER
    assert lib.r6_accessor_name(source, len(blob), 0,
                                text, 4) == R6_ERR_BUFFER
    assert lib.r6_accessor_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_accessor_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 6), (16, 154), (20, 0), (24, 35255)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_accessor_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 4182), (3, 179), (4, 1), (5, 31), (6, 31)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_accessor_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (2, 0), (4, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FUNC_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_accessor_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    print("Accessor negatives: bad magic/header/file/function fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, functions = acc.collect(args.dump)
    check(lib, files, functions, acc.build(files, functions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
