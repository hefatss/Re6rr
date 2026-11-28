"""ctypes checks for the packed TireInfo inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import tire_model_catalog as tir  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
FILE_SIZE = 32
SPAN_SIZE = 8
STRING_BASE = HEADER_SIZE + 240 * FILE_SIZE + 3840 * SPAN_SIZE
HEADER_FIELDS = ("version", "file_count", "span_count", "string_size",
                 "source_bytes")
FILE_FIELDS = ("path_offset", "path_length", "size", "lines", "span_base",
               "default_offset", "default_length", "color")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class File(ctypes.Structure):
    _fields_ = [(name, U32) for name in FILE_FIELDS]


class Span(ctypes.Structure):
    _fields_ = [("offset", U32), ("length", U32)]


def configure(lib):
    for name, args in (
        ("r6_tire_parse", [BUF, ctypes.c_size_t, ctypes.POINTER(Header)]),
        ("r6_tire_file", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(File)]),
        ("r6_tire_path", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_tire_span", [BUF, ctypes.c_size_t, U32, ctypes.POINTER(Span)]),
        ("r6_tire_text", [BUF, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]),
        ("r6_tire_default", [BUF, ctypes.c_size_t, U32, BUF,
                             ctypes.c_size_t])):
        func = getattr(lib, name)
        func.restype = ctypes.c_int
        func.argtypes = args


def check(lib, files, spans, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_tire_parse(source, len(blob),
                             ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 240, 3840, len(blob) - STRING_BASE, 165906]

    file = File()
    text = ctypes.create_string_buffer(96)
    for index, expected in enumerate(files):
        assert lib.r6_tire_file(source, len(blob), index,
                                ctypes.byref(file)) == R6_OK
        raw = struct.unpack_from("<8I", blob, HEADER_SIZE + index * FILE_SIZE)
        assert raw == tuple(getattr(file, name) for name in FILE_FIELDS)
        assert (file.size, file.lines, file.color) == \
            (expected[1], expected[2], expected[5])
        assert lib.r6_tire_path(source, len(blob), index,
                                text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[0]
        assert lib.r6_tire_default(source, len(blob), index,
                                   text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected[4]
    span = Span()
    for index, expected in enumerate(spans):
        assert lib.r6_tire_span(source, len(blob), index,
                                ctypes.byref(span)) == R6_OK
        assert struct.unpack_from("<2I", blob,
                                  HEADER_SIZE + 240 * FILE_SIZE +
                                  index * SPAN_SIZE) == \
            (span.offset, span.length)
        assert lib.r6_tire_text(source, len(blob), index,
                                text, len(text)) == R6_OK
        assert text.value.decode("ascii") == expected
    print("TireInfo: 240 files, 16 slots each, 1920 names, 1876 enums match")

    assert lib.r6_tire_file(source, len(blob), 240,
                            ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_tire_span(source, len(blob), 3840,
                            ctypes.byref(span)) == R6_ERR_ARG
    assert lib.r6_tire_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_tire_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_tire_path(source, len(blob), 0,
                            text, 4) == R6_ERR_BUFFER
    assert lib.r6_tire_parse(source, len(blob) - 1,
                             ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_tire_parse(source, len(bad),
                             ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 239), (16, 3839), (20, 0),
                        (24, 165905)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_tire_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 0), (3, 29), (4, 1), (7, 5)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_tire_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    # A required TIRE_ name becomes an enum token.
    bad = bytearray(blob)
    first = HEADER_SIZE + 240 * FILE_SIZE
    struct.pack_into("<I", bad, first + 4, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_tire_parse(source, len(bad),
                             ctypes.byref(header)) == R6_ERR_FORMAT
    print("TireInfo negatives: bad magic/header/file/span fields, "
          "out-of-range indexes, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, spans = tir.collect(args.dump)
    check(lib, files, spans, tir.build(files, spans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
