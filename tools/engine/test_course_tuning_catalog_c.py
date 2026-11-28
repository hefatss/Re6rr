"""ctypes checks for the packed course tuning inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import course_tuning_catalog as ctn  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
FILE_SIZE = 32
RAMP_SIZE = 32
TA_SIZE = 20
RAMP_BASE = HEADER_SIZE + 2 * FILE_SIZE
TA_BASE = RAMP_BASE + 39 * RAMP_SIZE
STRING_BASE = TA_BASE + 25 * TA_SIZE
HEADER_FIELDS = ("version", "file_count", "ramp_rows", "ta_rows",
                 "string_size", "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines",
               "global_offset", "global_length", "row_base", "rows")
RAMP_FIELDS = ("normal", "extreme", "gid_offset", "gid_length",
               "name_offset", "name_length", "alias_offset", "alias_length")
TA_FIELDS = ("value", "gid_offset", "gid_length", "name_offset",
             "name_length")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Ramp(ctypes.Structure):
    _fields_ = [(name, U32) for name in RAMP_FIELDS]


class Ta(ctypes.Structure):
    _fields_ = [(name, U32) for name in TA_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_course_tuning_parse", [BUF, ctypes.c_size_t,
                                    ctypes.POINTER(Header)]),
        ("r6_course_tuning_file", [BUF, ctypes.c_size_t, U32,
                                   ctypes.POINTER(File)]),
        ("r6_course_tuning_path", [BUF, ctypes.c_size_t, U32, BUF,
                                   ctypes.c_size_t]),
        ("r6_course_tuning_global", [BUF, ctypes.c_size_t, U32, BUF,
                                     ctypes.c_size_t]),
        ("r6_course_tuning_ramp_row", [BUF, ctypes.c_size_t, U32,
                                       ctypes.POINTER(Ramp)]),
        ("r6_course_tuning_ta_row", [BUF, ctypes.c_size_t, U32,
                                     ctypes.POINTER(Ta)]),
        ("r6_course_tuning_ramp_gid", [BUF, ctypes.c_size_t, U32, BUF,
                                       ctypes.c_size_t]),
        ("r6_course_tuning_ramp_name", [BUF, ctypes.c_size_t, U32, BUF,
                                        ctypes.c_size_t]),
        ("r6_course_tuning_ramp_alias", [BUF, ctypes.c_size_t, U32, BUF,
                                         ctypes.c_size_t]),
        ("r6_course_tuning_ta_gid", [BUF, ctypes.c_size_t, U32, BUF,
                                     ctypes.c_size_t]),
        ("r6_course_tuning_ta_name", [BUF, ctypes.c_size_t, U32, BUF,
                                      ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_course_tuning_parse(source, len(blob),
                                      ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 2, 39, 25, len(blob) - STRING_BASE, 5267]

    file = File()
    text = ctypes.create_string_buffer(96)
    for index, expected in enumerate(files):
        assert lib.r6_course_tuning_file(source, len(blob), index,
                                         ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<8I", blob,
                                 HEADER_SIZE + index * FILE_SIZE)
        assert raw == (file.path_offset, file.path_length, file.size,
                       file.lines, file.global_offset, file.global_length,
                       file.row_base, file.rows)
        assert (file.size, file.lines, file.rows) == \
            (expected[1], expected[2], len(expected[4]))
        assert lib.r6_course_tuning_path(source, len(blob), index,
                                         text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_course_tuning_global(source, len(blob), index,
                                           text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[3]

    ramp = Ramp()
    for index, expected in enumerate(files[0][4]):
        assert lib.r6_course_tuning_ramp_row(source, len(blob), index,
                                             ctypes.byref(ramp)) == R6_OK
        raw = struct.unpack_from("<8I", blob, RAMP_BASE + index * RAMP_SIZE)
        assert raw == tuple(getattr(ramp, name) for name in RAMP_FIELDS)
        assert (ramp.normal, ramp.extreme) == expected[:2]
        for getter, value in ((lib.r6_course_tuning_ramp_gid, expected[2]),
                              (lib.r6_course_tuning_ramp_name, expected[3]),
                              (lib.r6_course_tuning_ramp_alias, expected[4])):
            assert getter(source, len(blob), index,
                          text, len(text)) == R6_OK
            assert text.value.decode("ascii") == value

    ta = Ta()
    for index, expected in enumerate(files[1][4]):
        assert lib.r6_course_tuning_ta_row(source, len(blob), index,
                                           ctypes.byref(ta)) == R6_OK
        raw = struct.unpack_from("<5I", blob, TA_BASE + index * TA_SIZE)
        assert raw == tuple(getattr(ta, name) for name in TA_FIELDS)
        assert ta.value == expected[0]
        for getter, value in ((lib.r6_course_tuning_ta_gid, expected[1]),
                              (lib.r6_course_tuning_ta_name, expected[2])):
            assert getter(source, len(blob), index,
                          text, len(text)) == R6_OK
            assert text.value.decode("ascii") == value
    print("Course tuning: 2 files, 39 ramp rows and 25 TA rows match the dump")

    assert lib.r6_course_tuning_file(source, len(blob), 2,
                                     ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_course_tuning_ramp_row(source, len(blob), 39,
                                         ctypes.byref(ramp)) == R6_ERR_ARG
    assert lib.r6_course_tuning_ta_row(source, len(blob), 25,
                                       ctypes.byref(ta)) == R6_ERR_ARG
    assert lib.r6_course_tuning_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_course_tuning_file(source, len(blob), 0,
                                     None) == R6_ERR_ARG
    assert lib.r6_course_tuning_path(source, len(blob), 0,
                                     text, 4) == R6_ERR_BUFFER
    assert lib.r6_course_tuning_parse(source, len(blob) - 1,
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_course_tuning_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 1), (16, 38), (20, 24), (24, 0),
                        (28, 5266)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_course_tuning_parse(source, len(bad),
                                          ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 0), (5, 2), (6, 1), (7, 38)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_course_tuning_parse(source, len(bad),
                                          ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 10000), (2, 0), (4, 0), (6, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, RAMP_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_course_tuning_parse(source, len(bad),
                                          ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 10000), (1, 0), (3, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, TA_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_course_tuning_parse(source, len(bad),
                                          ctypes.byref(header)) == R6_ERR_FORMAT
    print("Course-tuning negatives: bad magic/header/file/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files = ctn.collect(args.dump)
    check(lib, files, ctn.build(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
