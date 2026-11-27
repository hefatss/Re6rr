"""ctypes checks for the packed root FBK/GBK WMBK bank inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import wmbk_bank_catalog as wbc  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
FILE_BASE = 32
FILE_SIZE = 44
RECORD_BASE = FILE_BASE + 20 * FILE_SIZE
RECORD_SIZE = 20


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("record_count", U32), ("string_size", U32),
                ("compressed_total", U32), ("inflated_total", U32)]


class File(ctypes.Structure):
    _fields_ = [("path_offset", U32), ("path_length", U32),
                ("compressed", U32), ("inflated", U32),
                ("mtime", U32), ("isize", U32),
                ("record_first", U32), ("record_count", U32),
                ("flg", U32), ("xfl", U32), ("os", U32)]


class Record(ctypes.Structure):
    _fields_ = [("file_index", U32), ("byte_offset", U32),
                ("magic", U32), ("version", U32),
                ("payload_length", U32)]


def configure(lib):
    lib.r6_wmbk_bank_parse.restype = ctypes.c_int
    lib.r6_wmbk_bank_parse.argtypes = [BUF, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_wmbk_bank_file.restype = ctypes.c_int
    lib.r6_wmbk_bank_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                      ctypes.POINTER(File)]
    lib.r6_wmbk_bank_path.restype = ctypes.c_int
    lib.r6_wmbk_bank_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                      ctypes.c_size_t]
    lib.r6_wmbk_bank_record.restype = ctypes.c_int
    lib.r6_wmbk_bank_record.argtypes = [BUF, ctypes.c_size_t, U32,
                                        ctypes.POINTER(Record)]


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_wmbk_bank_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.record_count) == (
        1, len(files), sum(len(row[8]) for row in files))
    assert header.compressed_total == sum(row[1] for row in files)
    assert header.inflated_total == sum(row[2] for row in files)
    assert header.string_size == len(blob) - RECORD_BASE - \
        header.record_count * RECORD_SIZE

    file = File()
    path = ctypes.create_string_buffer(96)
    expected_records = []
    for index, row in enumerate(files):
        name, compressed, inflated, mtime, isize, flg, xfl, os_byte, rows = row
        assert lib.r6_wmbk_bank_file(
            source, len(blob), index, ctypes.byref(file)) == R6_OK
        assert lib.r6_wmbk_bank_path(
            source, len(blob), index, path, len(path)) == R6_OK
        assert path.value.decode("ascii") == name
        assert (file.compressed, file.inflated, file.mtime, file.isize) == (
            compressed, inflated, mtime, isize)
        assert (file.flg, file.xfl, file.os) == (flg, xfl, os_byte)
        assert (file.record_count, file.record_first) == (
            len(rows), len(expected_records))
        for byte_offset, magic, version, payload in rows:
            expected_records.append((index, byte_offset, magic, version,
                                     payload))
    record = Record()
    for index, row in enumerate(expected_records):
        assert lib.r6_wmbk_bank_record(
            source, len(blob), index, ctypes.byref(record)) == R6_OK
        assert (record.file_index, record.byte_offset, record.magic,
                record.version, record.payload_length) == row
    print("WMBK banks: 20 gzip headers and all 22 WMBK records match the dump")

    assert lib.r6_wmbk_bank_file(
        source, len(blob), len(files), ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_wmbk_bank_path(
        source, len(blob), len(files), path, len(path)) == R6_ERR_ARG
    assert lib.r6_wmbk_bank_record(
        source, len(blob), len(expected_records),
        ctypes.byref(record)) == R6_ERR_ARG
    assert lib.r6_wmbk_bank_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_wmbk_bank_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_wmbk_bank_record(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_wmbk_bank_path(
        source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_wmbk_bank_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_wmbk_bank_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 19), (16, 21), (20, 1),
                        (24, 1669), (28, 5671)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_wmbk_bank_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((4, 0), (8, 0xffffffff), (32, 1), (36, 1),
                        (40, 254), (28, 22)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_wmbk_bank_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 1), (4, 4), (8, 0), (12, 2), (16, 11)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, RECORD_BASE + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_wmbk_bank_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    print("WMBK negatives: bad magic/header/file/record fields, truncation "
          "and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = wbc.collect(args.dump)
    check(lib, files, wbc.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
