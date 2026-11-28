"""ctypes checks for the packed sugoroku board inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import sugoroku_board_catalog as sbc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 40
CATEGORY_SIZE = 24
PAGE_SIZE = 64
FUNCTION_SIZE = 8
PAGE_BASE = HEADER_SIZE + 6 * CATEGORY_SIZE
FUNCTION_BASE = PAGE_BASE + 14 * PAGE_SIZE
HEADER_FIELDS = ("version", "category_count", "stage_count", "page_count",
                 "function_count", "item_count", "square_count", "string_size")
PAGE_FIELDS = ("stage", "page", "squares")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in HEADER_FIELDS]


class Category(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "name_offset", "name_length", "groups", "ids", "id_min", "id_max")]


class Page(ctypes.Structure):
    _fields_ = [("stage", U32), ("page", U32), ("squares", U32),
                ("tokens", U32 * 7), ("rewards", U32 * 6)]


def configure(lib):
    lib.r6_sugoroku_parse.restype = ctypes.c_int
    lib.r6_sugoroku_parse.argtypes = [BUF, ctypes.c_size_t,
                                      ctypes.POINTER(Header)]
    lib.r6_sugoroku_category.restype = ctypes.c_int
    lib.r6_sugoroku_category.argtypes = [BUF, ctypes.c_size_t, U32,
                                        ctypes.POINTER(Category)]
    lib.r6_sugoroku_page.restype = ctypes.c_int
    lib.r6_sugoroku_page.argtypes = [BUF, ctypes.c_size_t, U32,
                                    ctypes.POINTER(Page)]
    lib.r6_sugoroku_function.restype = ctypes.c_int
    lib.r6_sugoroku_function.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                        ctypes.c_size_t]


def check(lib, collection, blob):
    categories, pages, functions = collection
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_sugoroku_parse(source, len(blob),
                                 ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in HEADER_FIELDS] == [
        1, 6, 7, 14, 6, 115, 361, len(blob) - 1128]

    category = Category()
    for index, expected in enumerate(categories):
        assert lib.r6_sugoroku_category(source, len(blob), index,
                                        ctypes.byref(category)) == R6_OK
        assert struct.unpack_from("<6I", blob, HEADER_SIZE + index * 24) == (
            category.name_offset, category.name_length, category.groups,
            category.ids, category.id_min, category.id_max)
        assert (category.groups, category.ids, category.id_min,
                category.id_max) == expected[1:]
        assert ctypes.string_at(ctypes.addressof(source) +
                                category.name_offset,
                                category.name_length).decode("ascii") == \
            expected[0]

    page = Page()
    for index, expected in enumerate(pages):
        assert lib.r6_sugoroku_page(source, len(blob), index,
                                    ctypes.byref(page)) == R6_OK
        raw = struct.unpack_from("<16I", blob, PAGE_BASE + index * 64)
        assert raw == (page.stage, page.page, page.squares) + \
            tuple(page.tokens) + tuple(page.rewards)
        assert (page.stage, page.page, page.squares) == expected[:3]
        assert tuple(page.tokens) == expected[3]
        assert tuple(page.rewards) == expected[4]

    name = ctypes.create_string_buffer(64)
    for index, expected in enumerate(functions):
        assert lib.r6_sugoroku_function(source, len(blob), index,
                                        name, len(name)) == R6_OK
        assert name.value.decode("ascii") == expected
    print("Sugoroku: 6 categories, 14 pages, 361 squares and 6 Lua "
          "function names match the dump")

    assert lib.r6_sugoroku_category(source, len(blob), 6,
                                    ctypes.byref(category)) == R6_ERR_ARG
    assert lib.r6_sugoroku_page(source, len(blob), 14,
                                ctypes.byref(page)) == R6_ERR_ARG
    assert lib.r6_sugoroku_function(source, len(blob), 6,
                                    name, len(name)) == R6_ERR_ARG
    assert lib.r6_sugoroku_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_sugoroku_category(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_sugoroku_page(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_sugoroku_function(source, len(blob), 0, name, 4) == \
        R6_ERR_BUFFER
    assert lib.r6_sugoroku_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_sugoroku_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 5), (16, 6), (20, 13), (24, 5),
                        (28, 114), (32, 360), (36, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_sugoroku_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 0), (3, 0), (3, 115), (4, 200), (5, 22)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_sugoroku_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((2, 0), (3, 0), (3, 40), (4, 0), (10, 40)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, PAGE_BASE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_sugoroku_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    print("Sugoroku negatives: bad magic/header/category/page fields, "
          "truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    collection = sbc.collect(args.dump)
    check(lib, collection, sbc.build(collection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
