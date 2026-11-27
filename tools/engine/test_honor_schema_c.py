"""Check the C honor schema reader against recon and shipped pointer names."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import honor_schema_catalog  # noqa: E402
import native_names_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [("type_count", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


def check(dump, lib):
    lib.r6_honor_schema_parse.restype = ctypes.c_int
    lib.r6_honor_schema_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_honor_schema_type.restype = ctypes.c_int
    lib.r6_honor_schema_type.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_uint32, ctypes.c_char_p,
                                         ctypes.c_size_t,
                                         ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_honor_schema_find_type.restype = ctypes.c_int
    lib.r6_honor_schema_find_type.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                              ctypes.c_char_p,
                                              ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_honor_schema_field.restype = ctypes.c_int
    lib.r6_honor_schema_field.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_char_p, ctypes.c_size_t]
    lib.r6_honor_schema_find_field.restype = ctypes.c_int
    lib.r6_honor_schema_find_field.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32,
        ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32)]

    rows = honor_schema_catalog.collect()
    blob = honor_schema_catalog.build(rows)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_honor_schema_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert header.type_count == 13
    assert header.strings_off == 24 + 13 * 28
    assert header.strings_off + header.strings_size == len(blob)

    shipped = native_names_catalog.collect(dump)["check_honor"]
    name = ctypes.create_string_buffer(NAME_CAP)
    count = ctypes.c_uint32()
    fields = 0
    for index, row in enumerate(rows):
        assert lib.r6_honor_schema_type(source, len(blob), index, name,
                                        len(name), ctypes.byref(
                                            count)) == R6_OK
        assert name.value.decode("ascii") == row["name"] == shipped[index]
        assert count.value == len(row["fields"])
        for field, want in enumerate(row["fields"]):
            assert lib.r6_honor_schema_field(source, len(blob), index, field,
                                             name, len(name)) == R6_OK
            assert name.value.decode("ascii") == want
            found_field = ctypes.c_uint32()
            assert lib.r6_honor_schema_find_field(
                source, len(blob), index, want.encode("ascii"),
                ctypes.byref(found_field)) == R6_OK
            assert found_field.value == field
            fields += 1
    assert fields == 60

    found = ctypes.c_uint32()
    for index, row in enumerate(rows):
        assert lib.r6_honor_schema_find_type(
            source, len(blob), row["name"].encode("ascii"),
            ctypes.byref(found)) == R6_OK
        assert found.value == index
    assert lib.r6_honor_schema_find_type(
        source, len(blob), b"R6_NO_SUCH_TYPE",
        ctypes.byref(found)) == R6_ERR_NOT_FOUND
    absent_field = ctypes.c_uint32()
    assert lib.r6_honor_schema_find_field(
        source, len(blob), 0, b"R6_NO_SUCH_FIELD",
        ctypes.byref(absent_field)) == R6_ERR_NOT_FOUND
    assert lib.r6_honor_schema_find_field(
        source, len(blob), 13, b"car",
        ctypes.byref(absent_field)) == R6_ERR_ARG

    assert lib.r6_honor_schema_type(source, len(blob), 13, name, len(name),
                                    None) == R6_ERR_ARG
    assert lib.r6_honor_schema_field(source, len(blob), 0, 5, name,
                                     len(name)) == R6_ERR_ARG
    assert lib.r6_honor_schema_type(source, len(blob), 0, name, 4,
                                    None) == R6_ERR_BUFFER
    assert lib.r6_honor_schema_type(source, len(blob), 0, None, len(name),
                                    None) == R6_ERR_ARG
    assert lib.r6_honor_schema_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_honor_schema_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 12)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_honor_schema_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24 + 4, 6)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_honor_schema_type(source, len(bad), 0, name, len(name),
                                    None) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24 + 8, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_honor_schema_field(source, len(bad), 0, 0, name,
                                     len(name)) == R6_ERR_FORMAT
    print("honor schema: 13 shipped type names and 60 ordered fields match "
          "STORY_NATIVE.md and the exe pointer table; type/field find, "
          "bad blob, type, field and capacity rejected")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(args.dump, lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
