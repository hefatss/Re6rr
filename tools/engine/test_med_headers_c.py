"""ctypes checks for the validated .MED header reader."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import med_headers_catalog as mh  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("count", U32),
                ("header_off", U32), ("strings_size", U32)]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "file_size", "frames", "word0", "word2", "word3", "word4",
        "word5", "word6", "word7")]


def configure(lib):
    lib.r6_med_parse.restype = ctypes.c_int
    lib.r6_med_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                 ctypes.POINTER(Header)]
    lib.r6_med_row.restype = ctypes.c_int
    lib.r6_med_row.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                               ctypes.POINTER(Row)]
    lib.r6_med_path.restype = ctypes.c_int
    lib.r6_med_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                ctypes.c_char_p, ctypes.c_size_t]


def check(lib, data, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_med_parse(source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.count, header.header_off,
            header.strings_size) == (
        1, len(data), mh.HEADER_OFF,
        len(blob) - 24 - len(data) * mh.RECORD.size)

    row = Row()
    path = ctypes.create_string_buffer(256)
    for index, (want_path, want_size, words) in enumerate(data):
        assert lib.r6_med_row(source, len(blob), index,
                              ctypes.byref(row)) == R6_OK
        assert (row.file_size, row.frames, row.word0, row.word2, row.word3,
                row.word4, row.word5, row.word6, row.word7) == (
            want_size, words[1], words[0], words[2], words[3], words[4],
            words[5], words[6], words[7])
        assert lib.r6_med_path(source, len(blob), index, path,
                               len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
    print("MED headers: %d validated 0x100 headers, paths and file sizes "
          "match the dump" % len(data))

    assert lib.r6_med_row(source, len(blob), len(data),
                          ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_med_path(source, len(blob), len(data), path,
                           len(path)) == R6_ERR_ARG
    assert lib.r6_med_path(source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_med_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_med_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_med_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_med_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    for offset, value in ((8, 2), (16, 0x200)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, offset, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_med_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for offset, value in ((12, 1), (20, 409), (24, 2561),
                          (32, 77), (28, 1), (36, 1), (40, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, 24 + offset, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_med_row(source, len(bad), 0,
                              ctypes.byref(row)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_med_path(source, len(bad), 0, path,
                           len(path)) == R6_ERR_FORMAT
    print("MED header negatives: bad magic/version/offset/counts/derived "
          "sizes, truncation, bad path, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    data = mh.collect(args.dump)
    check(lib, data, mh.build(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
