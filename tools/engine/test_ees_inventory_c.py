"""ctypes checks for the packed .EES scene-header inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ees_inventory_catalog as ec  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("array_count", U32), ("strings_size", U32)]


class File(ctypes.Structure):
    _fields_ = [("file_size", U32), ("kind", U32), ("version", U32),
                ("count", U32), ("effect_count", U32),
                ("header_size", U32), ("array_first", U32),
                ("array_count", U32)]


class Array(ctypes.Structure):
    _fields_ = [("count", U32), ("stride", U32), ("offset", U32),
                ("size", U32)]


def configure(lib):
    lib.r6_ees_inventory_parse.restype = ctypes.c_int
    lib.r6_ees_inventory_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                           ctypes.POINTER(Header)]
    lib.r6_ees_inventory_file.restype = ctypes.c_int
    lib.r6_ees_inventory_file.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          U32, ctypes.POINTER(File)]
    lib.r6_ees_inventory_path.restype = ctypes.c_int
    lib.r6_ees_inventory_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          U32, BUF, ctypes.c_size_t]
    lib.r6_ees_inventory_array.restype = ctypes.c_int
    lib.r6_ees_inventory_array.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                           U32, BUF, ctypes.c_size_t,
                                           ctypes.POINTER(Array)]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_ees_inventory_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    arrays = sum(len(row[7]) for row in rows)
    assert (header.version, header.file_count, header.array_count,
            header.strings_size) == (
        1, len(rows), arrays,
        len(blob) - 24 - len(rows) * 44 - arrays * 24)

    file = File()
    path = ctypes.create_string_buffer(256)
    name = ctypes.create_string_buffer(64)
    array = Array()
    names = {}
    first = 0
    for index, row in enumerate(rows):
        want_path, kind, version, size, count, effect, header_size, values = row
        assert lib.r6_ees_inventory_file(
            source, len(blob), index, ctypes.byref(file)) == R6_OK
        assert (file.file_size, file.kind, file.version, file.count,
                file.effect_count, file.header_size, file.array_first,
                file.array_count) == (
            size, ec.KINDS.index(kind), version, count, effect,
            header_size, first, len(values))
        assert lib.r6_ees_inventory_path(
            source, len(blob), index, path, len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
        for local, value in enumerate(values):
            assert lib.r6_ees_inventory_array(
                source, len(blob), first + local, name, len(name),
                ctypes.byref(array)) == R6_OK
            assert name.value.decode("ascii") == value[0]
            assert (array.count, array.stride, array.offset, array.size) == (
                value[1:])
            names[value[0]] = names.get(value[0], 0) + 1
        first += len(values)
    assert names == {"camera_info": 720, "camera_data": 720,
                     "car_disp": 409, "car_effect": 409, "car_info": 409}
    print("EES inventory: 1129 files, 2667 arrays, paths and header facts "
          "match the dump")

    assert lib.r6_ees_inventory_file(
        source, len(blob), len(rows), ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_ees_inventory_path(
        source, len(blob), len(rows), path, len(path)) == R6_ERR_ARG
    assert lib.r6_ees_inventory_array(
        source, len(blob), first, name, len(name),
        ctypes.byref(array)) == R6_ERR_ARG
    assert lib.r6_ees_inventory_path(source, len(blob), 0, path,
                                     4) == R6_ERR_BUFFER
    assert lib.r6_ees_inventory_array(source, len(blob), 0, name, 4,
                                      ctypes.byref(array)) == R6_ERR_BUFFER
    assert lib.r6_ees_inventory_file(source, len(blob), 0,
                                     None) == R6_ERR_ARG
    assert lib.r6_ees_inventory_parse(source, len(blob),
                                      None) == R6_ERR_ARG
    assert lib.r6_ees_inventory_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ees_inventory_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1128), (16, 2666), (20, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_ees_inventory_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for kind, version, count, header_size, arrays in (
            (0, 10004, 1, 424, 2), (1, 10003, 1, 444, 3),
            (2, 10002, 1, 424, 2), (0, 10002, 0, 424, 2)):
        bad = bytearray(blob)
        struct.pack_into("<5I", bad, 24 + 4,
                         kind, version, count, 0, header_size)
        struct.pack_into("<I", bad, 24 + 36, arrays)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_ees_inventory_file(
            source, len(bad), 0, ctypes.byref(file)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ees_inventory_path(source, len(bad), 0, path,
                                     len(path)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    array_row = 24 + len(rows) * 44
    struct.pack_into("<I", bad, array_row + 12, 0x10)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ees_inventory_array(
        source, len(bad), 0, name, len(name),
        ctypes.byref(array)) == R6_ERR_FORMAT
    print("EES negatives: bad magic/counts/kinds/arrays, truncation, bad "
          "paths, out-of-range index, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = ec.collect(args.dump)
    check(lib, rows, ec.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
