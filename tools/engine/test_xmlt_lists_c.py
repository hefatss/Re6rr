"""ctypes checks for the packed XMLT list/seed/field inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_engine  # noqa: E402
import xmlt_lists_catalog as xlc  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("file_count", U32),
                ("list_count", U32), ("seed_count", U32),
                ("field_count", U32), ("type_count", U32),
                ("tag_count", U32), ("string_size", U32),
                ("reserved", U32)]


class File(ctypes.Structure):
    _fields_ = [("list_first", U32), ("list_count", U32)]


class List(ctypes.Structure):
    _fields_ = [("type_index", U32), ("seed_first", U32),
                ("seed_count", U32), ("field_first", U32),
                ("field_count", U32)]


class Seed(ctypes.Structure):
    _fields_ = [("list_index", U32), ("field_first", U32),
                ("field_count", U32)]


class Field(ctypes.Structure):
    _fields_ = [("seed_index", U32), ("tag_index", U32)]


def configure(lib):
    lib.r6_xmlt_lists_parse.restype = ctypes.c_int
    lib.r6_xmlt_lists_parse.argtypes = [BUF, ctypes.c_size_t,
                                        ctypes.POINTER(Header)]
    lib.r6_xmlt_file.restype = ctypes.c_int
    lib.r6_xmlt_file.argtypes = [BUF, ctypes.c_size_t, U32,
                                 ctypes.POINTER(File)]
    lib.r6_xmlt_path.restype = ctypes.c_int
    lib.r6_xmlt_path.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                 ctypes.c_size_t]
    lib.r6_xmlt_list.restype = ctypes.c_int
    lib.r6_xmlt_list.argtypes = [BUF, ctypes.c_size_t, U32,
                                 ctypes.POINTER(List)]
    lib.r6_xmlt_type.restype = ctypes.c_int
    lib.r6_xmlt_type.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                 ctypes.c_size_t]
    lib.r6_xmlt_seed.restype = ctypes.c_int
    lib.r6_xmlt_seed.argtypes = [BUF, ctypes.c_size_t, U32,
                                 ctypes.POINTER(Seed)]
    lib.r6_xmlt_field.restype = ctypes.c_int
    lib.r6_xmlt_field.argtypes = [BUF, ctypes.c_size_t, U32,
                                  ctypes.POINTER(Field)]
    lib.r6_xmlt_tag.restype = ctypes.c_int
    lib.r6_xmlt_tag.argtypes = [BUF, ctypes.c_size_t, U32, BUF,
                                ctypes.c_size_t]


def check(lib, files, lists, seeds, fields, types, tags, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_xmlt_lists_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.file_count, header.list_count,
            header.seed_count, header.field_count, header.type_count,
            header.tag_count, header.reserved) == (
        1, len(files), len(lists), len(seeds), len(fields), len(types),
        len(tags), 0)
    assert header.string_size == (len(blob) - 44 - len(files) * 16 -
                                  len(lists) * 20 - len(seeds) * 12 -
                                  len(fields) * 8)

    file = File()
    path = ctypes.create_string_buffer(96)
    for index, row in enumerate(files):
        assert lib.r6_xmlt_file(source, len(blob), index,
                                ctypes.byref(file)) == R6_OK
        assert (file.list_first, file.list_count) == row[1:]
        assert lib.r6_xmlt_path(source, len(blob), index, path,
                                len(path)) == R6_OK
        assert path.value.decode("ascii") == row[0]
    listing = List()
    name = ctypes.create_string_buffer(64)
    for index, row in enumerate(lists):
        assert lib.r6_xmlt_list(source, len(blob), index,
                                ctypes.byref(listing)) == R6_OK
        assert (listing.type_index, listing.seed_first, listing.seed_count,
                listing.field_first, listing.field_count) == row
        assert lib.r6_xmlt_type(source, len(blob), row[0], name,
                                len(name)) == R6_OK
        assert name.value.decode("ascii") == types[row[0]]
    seed = Seed()
    for index, row in enumerate(seeds):
        assert lib.r6_xmlt_seed(source, len(blob), index,
                                ctypes.byref(seed)) == R6_OK
        assert (seed.list_index, seed.field_first, seed.field_count) == row
    field = Field()
    for index, row in enumerate(fields):
        assert lib.r6_xmlt_field(source, len(blob), index,
                                 ctypes.byref(field)) == R6_OK
        assert (field.seed_index, field.tag_index) == row
        assert lib.r6_xmlt_tag(source, len(blob), row[1], name,
                               len(name)) == R6_OK
        assert name.value.decode("ascii") == tags[row[1]]
    print("XMLT catalog: 591 files, 3482 lists, 4432 seeds and 16544 field "
          "tags match the dump")

    assert lib.r6_xmlt_file(source, len(blob), len(files),
                            ctypes.byref(file)) == R6_ERR_ARG
    assert lib.r6_xmlt_path(source, len(blob), len(files), path,
                            len(path)) == R6_ERR_ARG
    assert lib.r6_xmlt_list(source, len(blob), len(lists),
                            ctypes.byref(listing)) == R6_ERR_ARG
    assert lib.r6_xmlt_type(source, len(blob), len(types), name,
                            len(name)) == R6_ERR_ARG
    assert lib.r6_xmlt_seed(source, len(blob), len(seeds),
                            ctypes.byref(seed)) == R6_ERR_ARG
    assert lib.r6_xmlt_field(source, len(blob), len(fields),
                             ctypes.byref(field)) == R6_ERR_ARG
    assert lib.r6_xmlt_tag(source, len(blob), len(tags), name,
                           len(name)) == R6_ERR_ARG
    assert lib.r6_xmlt_path(source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_xmlt_type(source, len(blob), 0, name, 3) == R6_ERR_BUFFER
    assert lib.r6_xmlt_tag(source, len(blob), 0, name, 3) == R6_ERR_BUFFER
    assert lib.r6_xmlt_file(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_xmlt_lists_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_xmlt_lists_parse(source, len(blob) - 1,
                                   ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmlt_lists_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 590), (16, 3481), (20, 4431),
                        (24, 16543), (28, 24), (32, 29), (36, 1),
                        (40, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmlt_lists_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT

    file_base = 44
    bad = bytearray(blob)
    struct.pack_into("<I", bad, file_base + 8, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_xmlt_lists_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    list_base = file_base + len(files) * 16
    for slot, value in ((0, 25), (4, 4433), (8, 1), (12, 16545), (16, 1)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, list_base + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmlt_lists_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    seed_base = list_base + len(lists) * 20
    for slot, value in ((0, 3482), (4, 16545), (8, 0)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, seed_base + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmlt_lists_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    field_base = seed_base + len(seeds) * 12
    for slot, value in ((0, 4432), (4, 30)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, field_base + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_xmlt_lists_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    print("XMLT negatives: bad magic/header/ranges, truncation, null outputs "
          "and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--assets", default=xlc.ASSETS_REPORT)
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    files, lists, seeds, fields, types, tags = xlc.collect(args.dump,
                                                            args.assets)
    check(lib, files, lists, seeds, fields, types, tags,
          xlc.build(files, lists, seeds, fields, types, tags))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
