"""ctypes checks for the packed .nut file-level header inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nut_file_catalog as nfc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
U64 = ctypes.c_uint64
BUF = ctypes.c_char_p
FILE_BASE = 44
FILE_SIZE = 76

FIELDS = ["path_offset", "path_length", "source_size", "inflated_size",
          "compressed", "container", "version", "entries", "total_lo",
          "total_hi", "payload_size", "descriptor_size", "packed0",
          "packed1", "gidx_lo", "gidx_hi", "payload_offset_lo",
          "payload_offset_hi", "exact"]


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("string_size", U32), ("source_bytes", U64),
                ("inflated_bytes", U64), ("gzip_count", U32),
                ("exact_count", U32)]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_nut_file_parse.restype = ctypes.c_int
    lib.r6_nut_file_parse.argtypes = [BUF, ctypes.c_size_t,
                                      ctypes.POINTER(Header)]
    lib.r6_nut_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                ctypes.POINTER(File)]
    lib.r6_nut_file.restype = ctypes.c_int
    lib.r6_nut_file_path.restype = ctypes.c_int
    lib.r6_nut_file_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                     ctypes.c_size_t]


def check(lib, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_nut_file_parse(source, len(blob),
                                 ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count) == (1, len(rows))
    assert header.string_size == len(blob) - nfc.HEADER.size - \
        len(rows) * nfc.FILE.size
    assert (header.source_bytes, header.inflated_bytes) == (
        sum(row[1] for row in rows), sum(row[2] for row in rows))
    assert (header.gzip_count, header.exact_count) == (
        sum(row[3] for row in rows), sum(row[-1] for row in rows))

    file = File()
    path = ctypes.create_string_buffer(160)
    for index, row in enumerate(rows):
        fields = struct.unpack_from("<19I", blob,
                                    FILE_BASE + index * FILE_SIZE)
        assert lib.r6_nut_file(source, len(blob), index,
                               ctypes.byref(file)) == R6_OK
        assert lib.r6_nut_file_path(source, len(blob), index, path,
                                    len(path)) == R6_OK
        assert path.value.decode("ascii") == row[0]
        assert [getattr(file, name) for name in FIELDS] == list(fields)
        assert fields[2:8] == row[1:7]
        assert fields[8] | (fields[9] << 32) == row[7]
        assert fields[10:14] == row[8:12]
        assert fields[14] | (fields[15] << 32) == row[12]
        assert fields[16] | (fields[17] << 32) == row[13]
        assert fields[18] == row[14]
    print("NUT files: all 11151 paths and file-level headers match the dump")

    assert lib.r6_nut_file(source, len(blob), len(rows),
                           ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_nut_file_path(source, len(blob), len(rows), path,
                                len(path)) == R6_ERR_ARG
    assert lib.r6_nut_file_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_nut_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_nut_file_path(source, len(blob), 0, path, 4) == \
        R6_ERR_BUFFER
    assert lib.r6_nut_file_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nut_file_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 11150), (16, 1), (20, 1), (24, 1),
                        (36, 5573), (40, 9598)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_nut_file_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for field, value in (("compressed", 2), ("container", 0), ("version", 3),
                         ("entries", 0), ("descriptor_size", 0x40),
                         ("source_size", 0), ("payload_offset_lo", 0),
                         ("total_hi", 1), ("exact", 2)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + FIELDS.index(field) * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_nut_file_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    inexact = next(index for index, row in enumerate(rows) if not row[-1])
    bad = bytearray(blob)
    struct.pack_into("<I", bad, FILE_BASE + inexact * FILE_SIZE +
                     FIELDS.index("exact") * 4, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nut_file_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    path_offset, path_length = struct.unpack_from(
        "<2I", blob, FILE_BASE)
    bad = bytearray(blob)
    bad[path_offset + path_length - 1] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nut_file_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    print("NUT negatives: bad magic/header/file fields, truncation and short "
          "buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    rows = nfc.collect(args.dump)
    check(lib, rows, nfc.build(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
