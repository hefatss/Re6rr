"""ctypes checks for the packed course route and path-bin inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import course_paths_catalog as cpc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("route_count", U32), ("ref_count", U32),
                ("file_count", U32), ("strings_size", U32)]


class File(ctypes.Structure):
    _fields_ = [("file_size", U32), ("triple_count", U32)]


class Route(ctypes.Structure):
    _fields_ = [("area_id", U32), ("loop", U32),
                ("camera_direction", U32), ("path_first", U32),
                ("path_count", U32)]


def configure(lib):
    lib.r6_course_paths_parse.restype = ctypes.c_int
    lib.r6_course_paths_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_course_paths_file.restype = ctypes.c_int
    lib.r6_course_paths_file.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                         U32, ctypes.POINTER(File)]
    lib.r6_course_paths_path.restype = ctypes.c_int
    lib.r6_course_paths_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                         U32, BUF, ctypes.c_size_t]
    lib.r6_course_paths_route.restype = ctypes.c_int
    lib.r6_course_paths_route.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                          U32, ctypes.POINTER(Route)]
    lib.r6_course_paths_route_name.restype = ctypes.c_int
    lib.r6_course_paths_route_name.argtypes = [ctypes.c_char_p,
                                               ctypes.c_size_t, U32, BUF,
                                               ctypes.c_size_t]
    lib.r6_course_paths_route_ref.restype = ctypes.c_int
    lib.r6_course_paths_route_ref.argtypes = [ctypes.c_char_p,
                                              ctypes.c_size_t, U32, BUF,
                                              ctypes.c_size_t]


def check(lib, routes, refs, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_course_paths_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.route_count, header.ref_count,
            header.file_count, header.strings_size) == (
        1, len(routes), len(refs), len(files),
        len(blob) - 28 - len(routes) * 28 - len(refs) * 8 - len(files) * 16)

    route = Route()
    file = File()
    name = ctypes.create_string_buffer(128)
    path = ctypes.create_string_buffer(256)
    first = 0
    for index, row in enumerate(routes):
        want_name, area, loop, direction, paths = row
        assert lib.r6_course_paths_route(
            source, len(blob), index, ctypes.byref(route)) == R6_OK
        assert (route.area_id, route.loop, route.camera_direction,
                route.path_first, route.path_count) == (
            area, loop, direction, first, len(paths))
        assert lib.r6_course_paths_route_name(
            source, len(blob), index, name, len(name)) == R6_OK
        assert name.value.decode("ascii") == want_name
        for local, want_ref in enumerate(paths):
            assert lib.r6_course_paths_route_ref(
                source, len(blob), first + local, name, len(name)) == R6_OK
            assert name.value.decode("ascii") == want_ref
        first += len(paths)
    assert first == len(refs)
    for index, (want_path, size, triples) in enumerate(files):
        assert lib.r6_course_paths_file(
            source, len(blob), index, ctypes.byref(file)) == R6_OK
        assert (file.file_size, file.triple_count) == (size, triples)
        assert lib.r6_course_paths_path(
            source, len(blob), index, path, len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
    print("Course paths: 33 routes, 143 path refs and 178 path bins match "
          "the dump")

    assert lib.r6_course_paths_route(
        source, len(blob), len(routes), ctypes.byref(route)) == R6_ERR_ARG
    assert lib.r6_course_paths_file(
        source, len(blob), len(files), ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_course_paths_route_ref(
        source, len(blob), len(refs), name, len(name)) == R6_ERR_ARG
    assert lib.r6_course_paths_route_name(source, len(blob), 0, name,
                                          4) == R6_ERR_BUFFER
    assert lib.r6_course_paths_path(source, len(blob), 0, path,
                                    4) == R6_ERR_BUFFER
    assert lib.r6_course_paths_route(source, len(blob), 0,
                                     None) == R6_ERR_ARG
    assert lib.r6_course_paths_parse(source, len(blob),
                                     None) == R6_ERR_ARG
    assert lib.r6_course_paths_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_course_paths_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 32), (16, 142), (20, 177), (24, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_course_paths_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((20, 143), (24, 143), (16, 2), (12, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, 28 + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_course_paths_route(
            source, len(bad), 0, ctypes.byref(route)) == R6_ERR_FORMAT
    file_row = 28 + len(routes) * 28 + len(refs) * 8
    bad = bytearray(blob)
    struct.pack_into("<I", bad, file_row + 8, files[0][1] + 12)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_course_paths_file(
        source, len(bad), 0, ctypes.byref(file)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, file_row, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_course_paths_path(source, len(bad), 0, path,
                                    len(path)) == R6_ERR_FORMAT
    print("Course path negatives: bad magic/counts/ranges/sizes, truncation, "
          "bad offsets, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    routes, refs, files = cpc.collect(args.dump)
    check(lib, routes, refs, files, cpc.build(routes, refs, files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
