"""ctypes checks for the packed carryover inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import carryover_catalog as cry  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 32
RECORD_SIZE = 16
ROW_SIZE = 60
ROW_BASE = HEADER_SIZE + 7 * RECORD_SIZE
STRING_BASE = ROW_BASE + 4 * ROW_SIZE
HEADER_FIELDS = ("version", "file_count", "record_count", "row_count",
                 "string_size", "source_bytes")
RECORD_FIELDS = ("text_offset", "text_length", "kind", "line")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Record(ctypes.Structure):
    _fields_ = [(name, U32) for name in RECORD_FIELDS]


class Row(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "bool_offset", "bool_length", "number_offset", "number_length",
        "token_offset", "token_length", "first_offset", "first_length",
        "second_offset", "second_length", "third_offset", "third_length",
        "tail_offset", "tail_length", "line")]


def configure(lib):
    for name, args in (
        ("r6_carryover_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_carryover_record", [BUF, ctypes.c_size_t, U32,
                                 ctypes.POINTER(Record)]),
        ("r6_carryover_text", [BUF, ctypes.c_size_t, U32, BUF,
                               ctypes.c_size_t]),
        ("r6_carryover_row", [BUF, ctypes.c_size_t, U32,
                              ctypes.POINTER(Row)]),
        ("r6_carryover_field", [BUF, ctypes.c_size_t, U32, U32, BUF,
                                ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, entry, blob):
    path, size, lines, preamble, rows = entry
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_carryover_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 1, 7, 4, len(blob) - STRING_BASE, 398]
    text = ctypes.create_string_buffer(64)
    record = Record()
    for index, expected in enumerate([(path, 2, 0)] + preamble):
        assert lib.r6_carryover_record(source, len(blob), index,
                                       ctypes.byref(record)) == R6_OK
        raw = struct.unpack_from("<4I", blob, HEADER_SIZE + index * RECORD_SIZE)
        assert raw == tuple(getattr(record, name) for name in RECORD_FIELDS)
        assert (record.kind, record.line) == (expected[1], expected[2])
        assert lib.r6_carryover_text(source, len(blob), index,
                                     text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
    row = Row()
    fields = []
    for name, _ in Row._fields_:
        fields.append(name)
    for index, expected in enumerate(rows):
        assert lib.r6_carryover_row(source, len(blob), index,
                                    ctypes.byref(row)) == R6_OK
        raw = struct.unpack_from("<15I", blob, ROW_BASE + index * ROW_SIZE)
        assert raw == tuple(getattr(row, name) for name in fields)
        assert row.line == expected[-1]
        for field, value in enumerate(expected[:-1]):
            assert lib.r6_carryover_field(source, len(blob), index, field,
                                          text, len(text)) == R6_OK
            assert text.value.decode("ascii") == value
    print("Carryover: 1 series token, 5 scalars and 4 rows match")

    assert lib.r6_carryover_record(source, len(blob), 7,
                                   ctypes.byref(record)) == R6_ERR_ARG
    assert lib.r6_carryover_text(source, len(blob), 7,
                                 text, len(text)) == R6_ERR_ARG
    assert lib.r6_carryover_row(source, len(blob), 4,
                                ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_carryover_field(source, len(blob), 0, 7,
                                  text, len(text)) == R6_ERR_ARG
    assert lib.r6_carryover_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_carryover_record(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_carryover_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_carryover_text(source, len(blob), 1,
                                 text, 4) == R6_ERR_BUFFER
    assert lib.r6_carryover_field(source, len(blob), 0, 0,
                                  text, 4) == R6_ERR_BUFFER
    assert lib.r6_carryover_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_carryover_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 2), (16, 6), (20, 3), (24, 0),
                        (28, 397)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_carryover_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (2, 3), (3, 9)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + RECORD_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_carryover_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((0, 0), (2, 0), (4, 0), (14, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, ROW_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_carryover_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    print("Carryover negatives: bad magic/header/record/row fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    entry = cry.collect(args.dump)
    check(lib, entry, cry.build(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
