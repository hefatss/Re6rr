"""ctypes checks for the packed Enma error-log layout inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import enma_error_log_catalog as eec  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 44
FILE_BASE = HEADER_SIZE
FILE_SIZE = 36
FIELDS = ["path_offset", "path_length", "size", "lines", "shape",
          "line_min", "line_max", "crlf", "tokens"]


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "version", "file_count", "string_size", "total_bytes", "total_lines",
        "crlf_count", "sector_lines", "vector_lines", "sector_files")]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_enma_error_log_parse.restype = ctypes.c_int
    lib.r6_enma_error_log_parse.argtypes = [BUF, ctypes.c_size_t,
                                            ctypes.POINTER(Header)]
    lib.r6_enma_error_log_file.restype = ctypes.c_int
    lib.r6_enma_error_log_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                           ctypes.POINTER(File)]
    lib.r6_enma_error_log_path.restype = ctypes.c_int
    lib.r6_enma_error_log_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                           ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_enma_error_log_parse(source, len(blob),
                                       ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count) == (1, len(rows))
    assert header.string_size == len(blob) - HEADER_SIZE - len(rows) * FILE_SIZE
    assert (header.total_bytes, header.total_lines, header.crlf_count) == (
        448033, 4010, 4010)
    assert (header.sector_lines, header.vector_lines,
            header.sector_files) == (23, 3987, 3)

    file = File()
    path = ctypes.create_string_buffer(96)
    for index, row in enumerate(rows):
        fields = struct.unpack_from("<9I", blob, FILE_BASE + index * FILE_SIZE)
        assert lib.r6_enma_error_log_file(source, len(blob), index,
                                          ctypes.byref(file)) == R6_OK
        assert lib.r6_enma_error_log_path(source, len(blob), index, path,
                                          len(path)) == R6_OK
        assert path.value.decode("ascii") == row[0]
        assert [getattr(file, name) for name in FIELDS] == list(fields)
        assert fields[2:9] == row[1:8]
    print("Enma error logs: 6 files, 4010 CRLF lines and copied layout facts "
          "match the dump")

    assert lib.r6_enma_error_log_file(source, len(blob), len(rows),
                                      ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_enma_error_log_path(source, len(blob), len(rows), path,
                                      len(path)) == R6_ERR_ARG
    assert lib.r6_enma_error_log_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_enma_error_log_file(source, len(blob), 0,
                                      None) == R6_ERR_ARG
    assert lib.r6_enma_error_log_path(source, len(blob), 0, path, 4) == \
        R6_ERR_BUFFER
    assert lib.r6_enma_error_log_parse(source, len(blob) - 1,
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_error_log_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 5), (16, 1), (20, 448032), (24, 4009),
                        (28, 4009), (32, 22), (36, 3986), (40, 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_enma_error_log_parse(source, len(bad),
                                           ctypes.byref(header)) == R6_ERR_FORMAT
    for index, value in ((2, 0), (3, 0), (4, 2), (5, 0), (6, 1), (7, 0),
                         (8, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + index * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_enma_error_log_parse(source, len(bad),
                                           ctypes.byref(header)) == R6_ERR_FORMAT
    print("Enma negatives: bad magic/header/file fields, truncation and short "
          "buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = eec.collect(args.dump)
    check(lib, rows, eec.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
