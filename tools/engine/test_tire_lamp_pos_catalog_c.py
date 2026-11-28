"""ctypes checks for the packed tire/lamp/strobo position inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import tire_lamp_pos_catalog as tlp  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 52
FILE_SIZE = 32
SECTION_SIZE = 32
ROW_SIZE = 16
FILE_BASE = HEADER_SIZE
SECTION_BASE = FILE_BASE + 255 * FILE_SIZE
ROW_BASE = SECTION_BASE + 28797 * SECTION_SIZE
STRING_BASE = ROW_BASE + 23759 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "section_count", "list_count",
                 "scalar_count", "row_count", "token_count", "line_count",
                 "source_bytes", "string_size", "reserved")
FILE_FIELDS = ("name_offset", "name_length", "car_id_offset", "car_id_length",
               "size", "lines", "section_base", "section_count")
SECTION_FIELDS = ("key_offset", "key_length", "line", "kind", "value_offset",
                  "value_length", "row_base", "row_count")
ROW_FIELDS = ("line", "token0_offset", "token1_offset", "token2_offset")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Section(ctypes.Structure):
    _fields_ = [(name, U32) for name in SECTION_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in ROW_FIELDS]


def configure(lib):
    for name, args in (
        ("r6_tlp_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_tlp_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_tlp_name", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_tlp_car_id", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_tlp_section", [BUF, ctypes.c_size_t, U32,
                            ctypes.POINTER(Section)]),
        ("r6_tlp_key", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_tlp_value", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_tlp_row", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Row)]),
        ("r6_tlp_token", [BUF, ctypes.c_size_t, U32, U32, BUF,
                          ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, sections, rows, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_tlp_parse(source, len(blob),
                            ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 255, 28797, 14775, 14022, 23759, 71277, 681731,
        22041850, len(blob) - STRING_BASE, 0]
    text = ctypes.create_string_buffer(96)
    file = File()
    for index, expected in enumerate(files):
        assert lib.r6_tlp_file(source, len(blob), index,
                               ctypes.byref(file)) == R6_OK
        packed = struct.unpack_from("<8I", blob, FILE_BASE + index * FILE_SIZE)
        assert packed == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.lines, file.section_base,
                file.section_count) == (expected[2], expected[3],
                                        expected[4], expected[5])
        assert lib.r6_tlp_name(source, len(blob), index,
                               text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_tlp_car_id(source, len(blob), index,
                                 text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[1].decode("ascii")
    section = Section()
    for index, expected in enumerate(sections):
        assert lib.r6_tlp_section(source, len(blob), index,
                                  ctypes.byref(section)) == R6_OK
        packed = struct.unpack_from("<8I", blob,
                                    SECTION_BASE + index * SECTION_SIZE)
        assert packed == tuple(getattr(section, name)
                               for name in SECTION_FIELDS)
        assert (section.line, section.kind, section.row_base,
                section.row_count) == (expected[1], expected[2],
                                       expected[4], expected[5])
        assert lib.r6_tlp_key(source, len(blob), index,
                              text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0].decode("ascii")
        if section.kind == 1:
            assert lib.r6_tlp_value(source, len(blob), index,
                                    text, len(text)) == R6_OK
            assert text.value.decode("ascii") == expected[3].decode("ascii")
        else:
            assert lib.r6_tlp_value(source, len(blob), index,
                                    text, len(text)) == R6_ERR_ARG
    row = Row()
    for index, expected in enumerate(rows):
        assert lib.r6_tlp_row(source, len(blob), index,
                              ctypes.byref(row)) == R6_OK
        packed = struct.unpack_from("<4I", blob, ROW_BASE + index * ROW_SIZE)
        assert packed == tuple(getattr(row, name) for name in ROW_FIELDS)
        assert row.line == expected[0]
        for slot, token in enumerate(expected[1]):
            assert lib.r6_tlp_token(source, len(blob), index, slot,
                                    text, len(text)) == R6_OK
            assert text.value.decode("ascii") == token.decode("ascii")
    print("Tire/lamp positions: 255 files, 28797 sections, 23759 rows and "
          "71277 tokens match")

    assert lib.r6_tlp_file(source, len(blob), 255, ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_tlp_section(source, len(blob), 28797,
                              ctypes.byref(section)) == R6_ERR_ARG
    assert lib.r6_tlp_row(source, len(blob), 23759, ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_tlp_token(source, len(blob), 0, 3,
                            text, len(text)) == R6_ERR_ARG
    assert lib.r6_tlp_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_tlp_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_tlp_name(source, len(blob), 0, text, 4) == R6_ERR_BUFFER
    assert lib.r6_tlp_token(source, len(blob), 0, 0,
                            text, 2) == R6_ERR_BUFFER
    assert lib.r6_tlp_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_tlp_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 254), (16, 28796), (20, 14774),
                        (24, 14021), (28, 23758), (32, 71276),
                        (36, 681730), (40, 22041849), (44, 0), (48, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_tlp_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 22041849), (3, 0), (5, 0), (6, 1), (7, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, FILE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_tlp_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((3, 2), (6, 23759), (7, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, SECTION_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_tlp_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_tlp_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    print("Tire/lamp negatives: bad magic/header/file/section/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, sections, rows = tlp.collect(args.dump)
    check(lib, files, sections, rows, tlp.build(files, sections, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
