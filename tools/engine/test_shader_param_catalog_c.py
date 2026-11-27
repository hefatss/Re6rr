"""ctypes checks for the packed per-car shader Lua parameter inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import shader_param_catalog as spc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
F32 = ctypes.c_float
BUF = ctypes.c_char_p
ROW = 28


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("count", U32), ("string_size", U32),
                ("reserved0", U32), ("reserved1", U32)]


class File(ctypes.Structure):
    _fields_ = [("path_offset", U32), ("path_length", U32),
                ("model_offset", U32), ("model_length", U32),
                ("values", F32 * 8)]


def configure(lib):
    lib.r6_shader_param_parse.restype = ctypes.c_int
    lib.r6_shader_param_parse.argtypes = [BUF, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_shader_param_file.restype = ctypes.c_int
    lib.r6_shader_param_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                         ctypes.POINTER(File)]
    lib.r6_shader_param_path.restype = ctypes.c_int
    lib.r6_shader_param_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                         ctypes.c_size_t]
    lib.r6_shader_param_model.restype = ctypes.c_int
    lib.r6_shader_param_model.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                          ctypes.c_size_t]


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_shader_param_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.count, header.string_size,
            header.reserved0, header.reserved1) == (
        1, len(rows), len(blob) - 28 - len(rows) * 48, 0, 0)

    file = File()
    path = ctypes.create_string_buffer(96)
    model = ctypes.create_string_buffer(64)
    for index, row in enumerate(rows):
        assert lib.r6_shader_param_file(
            source, len(blob), index, ctypes.byref(file)) == R6_OK
        assert lib.r6_shader_param_path(
            source, len(blob), index, path, len(path)) == R6_OK
        assert lib.r6_shader_param_model(
            source, len(blob), index, model, len(model)) == R6_OK
        assert path.value.decode("ascii") == row[0]
        assert model.value.decode("ascii") == row[1]
        assert (file.path_length, file.model_length) == (
            len(row[0]), len(row[1]))
        assert blob[file.path_offset:file.path_offset + file.path_length] == \
            row[0].encode("ascii")
        assert blob[file.model_offset:file.model_offset + file.model_length] == \
            row[1].encode("ascii")
        assert all(abs(file.values[at] - f32(value)) < 1e-6
                   for at, value in enumerate(row[2]))
    print("Shader parameters: all 142 Lua files, model names and 8 float "
          "values match the dump")

    assert lib.r6_shader_param_file(
        source, len(blob), len(rows), ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_shader_param_path(
        source, len(blob), len(rows), path, len(path)) == R6_ERR_ARG
    assert lib.r6_shader_param_model(
        source, len(blob), len(rows), model, len(model)) == R6_ERR_ARG
    assert lib.r6_shader_param_parse(
        source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_shader_param_file(
        source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_shader_param_path(
        source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_shader_param_model(
        source, len(blob), 0, model, 4) == R6_ERR_BUFFER
    assert lib.r6_shader_param_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_shader_param_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 141), (16, 1), (20, 1), (24, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_shader_param_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT

    for slot, value in ((0, 0), (4, 0), (8, 0), (12, 0),
                        (0, len(blob)), (8, len(blob))):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_shader_param_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT

    path_offset, path_length = struct.unpack_from("<2I", blob, ROW)
    model_offset = struct.unpack_from("<I", blob, ROW + 8)[0]
    for at, value in ((path_offset + path_length - 1, ord("X")),
                      (path_offset + path_length, ord("Z")),
                      (path_offset, 0x80), (model_offset, ord("X"))):
        bad = bytearray(blob)
        bad[at] = value
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_shader_param_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, ROW + 16, 0x7f800000)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_shader_param_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    print("Shader parameter negatives: bad magic/header/rows/paths/floats, "
          "truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = spc.collect(args.dump)
    check(lib, rows, spc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
