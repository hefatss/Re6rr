"""ctypes checks for the raw .MTMP model-table reader."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import mtmp_catalog as mc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("object_count", U32), ("strings_size", U32)]


class File(ctypes.Structure):
    _fields_ = [("file_size", U32), ("object_first", U32),
                ("object_count", U32)]


def configure(lib):
    lib.r6_mtmp_parse.restype = ctypes.c_int
    lib.r6_mtmp_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                  ctypes.POINTER(Header)]
    lib.r6_mtmp_file.restype = ctypes.c_int
    lib.r6_mtmp_file.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                 ctypes.POINTER(File)]
    lib.r6_mtmp_path.restype = ctypes.c_int
    lib.r6_mtmp_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                 BUF, ctypes.c_size_t]
    lib.r6_mtmp_scale.restype = ctypes.c_int
    lib.r6_mtmp_scale.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                  BUF, ctypes.c_size_t]
    lib.r6_mtmp_object.restype = ctypes.c_int
    lib.r6_mtmp_object.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                   BUF, ctypes.c_size_t]


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_mtmp_parse(source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.object_count,
            header.strings_size) == (
        1, len(files), sum(len(row[3]) for row in files),
        len(blob) - 24 - len(files) * 24 - sum(len(row[3]) for row in files) * 8)

    file = File()
    path = ctypes.create_string_buffer(256)
    scale = ctypes.create_string_buffer(128)
    object_line = ctypes.create_string_buffer(512)
    first = 0
    for index, (want_path, want_size, want_scale, objects) in enumerate(files):
        assert lib.r6_mtmp_file(source, len(blob), index,
                                ctypes.byref(file)) == R6_OK
        assert (file.file_size, file.object_first, file.object_count) == (
            want_size, first, len(objects))
        assert lib.r6_mtmp_path(source, len(blob), index, path,
                                len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
        assert lib.r6_mtmp_scale(source, len(blob), index, scale,
                                 len(scale)) == R6_OK
        assert scale.value.decode("ascii") == want_scale
        for local, want_object in enumerate(objects):
            assert lib.r6_mtmp_object(
                source, len(blob), first + local, object_line,
                len(object_line)) == R6_OK
            assert object_line.value.decode("ascii") == want_object
        first += len(objects)
    print("MTMP tables: %d files, %d object lines, paths and scales match "
          "the dump" % (len(files), first))

    assert lib.r6_mtmp_file(source, len(blob), len(files),
                            ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_mtmp_path(source, len(blob), len(files), path,
                            len(path)) == R6_ERR_ARG
    assert lib.r6_mtmp_scale(source, len(blob), len(files), scale,
                             len(scale)) == R6_ERR_ARG
    assert lib.r6_mtmp_object(source, len(blob), first, object_line,
                              len(object_line)) == R6_ERR_ARG
    assert lib.r6_mtmp_path(source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_mtmp_object(source, len(blob), 0, object_line,
                              4) == R6_ERR_BUFFER
    assert lib.r6_mtmp_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_mtmp_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_mtmp_parse(source, len(blob) - 1,
                             ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_mtmp_parse(source, len(bad),
                             ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 33), (16, 285), (20, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_mtmp_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24 + 16, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_mtmp_file(source, len(bad), 0,
                            ctypes.byref(file)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_mtmp_path(source, len(bad), 0, path,
                            len(path)) == R6_ERR_FORMAT
    print("MTMP negatives: bad magic/counts/ranges, truncation, bad paths, "
          "out-of-range index, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = mc.collect(args.dump)
    check(lib, files, mc.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
