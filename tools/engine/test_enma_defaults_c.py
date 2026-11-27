"""Check the C Enma SetDefault reader against the shipped DLL write probes."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import enma_defaults_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80
BYTE_CAP = 0x400


class Header(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32),
                ("fields_off", ctypes.c_uint32),
                ("data_off", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


def check(lib):
    lib.r6_enma_defaults_parse.restype = ctypes.c_int
    lib.r6_enma_defaults_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.POINTER(Header)]
    lib.r6_enma_defaults_struct.restype = ctypes.c_int
    lib.r6_enma_defaults_struct.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                            ctypes.c_uint32, ctypes.c_char_p,
                                            ctypes.c_size_t,
                                            ctypes.POINTER(ctypes.c_uint32),
                                            ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_enma_defaults_find.restype = ctypes.c_int
    lib.r6_enma_defaults_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_char_p,
                                           ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_enma_defaults_field.restype = ctypes.c_int
    lib.r6_enma_defaults_field.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_uint32, ctypes.c_uint32,
                                           ctypes.POINTER(ctypes.c_uint32),
                                           ctypes.POINTER(ctypes.c_uint32),
                                           ctypes.c_void_p, ctypes.c_size_t]
    lib.r6_enma_defaults_find_field.restype = ctypes.c_int
    lib.r6_enma_defaults_find_field.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32,
        ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]

    structs = enma_defaults_catalog.collect()
    blob = enma_defaults_catalog.build(structs)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_enma_defaults_parse(source, len(blob),
                                      ctypes.byref(header)) == R6_OK
    assert header.count == 32
    assert header.fields_off == 32 + 32 * 16
    assert header.data_off == header.fields_off + 89 * 16
    assert header.strings_off + header.strings_size == len(blob)

    name = ctypes.create_string_buffer(NAME_CAP)
    written = ctypes.c_uint32()
    count = ctypes.c_uint32()
    offset = ctypes.c_uint32()
    length = ctypes.c_uint32()
    payload = ctypes.create_string_buffer(BYTE_CAP)
    fields = 0
    byte_total = 0
    for index, item in enumerate(structs):
        assert lib.r6_enma_defaults_struct(source, len(blob), index, name,
                                           len(name), ctypes.byref(written),
                                           ctypes.byref(count)) == R6_OK
        assert name.value.decode("ascii") == item["name"]
        assert written.value == item["max_written"]
        assert count.value == len(item["fields"])
        for field_index, field in enumerate(item["fields"]):
            assert lib.r6_enma_defaults_field(
                source, len(blob), index, field_index,
                ctypes.byref(offset), ctypes.byref(length),
                payload, len(payload)) == R6_OK
            assert offset.value == field["offset"]
            assert length.value == field["size"]
            assert payload.raw[:length.value] == field["bytes"]
            found_field = ctypes.c_uint32()
            assert lib.r6_enma_defaults_find_field(
                source, len(blob), index, field["offset"],
                ctypes.byref(found_field)) == R6_OK
            assert found_field.value == field_index
            fields += 1
            byte_total += length.value
    assert (fields, byte_total) == (89, 2642)

    found = ctypes.c_uint32()
    for index, item in enumerate(structs):
        assert lib.r6_enma_defaults_find(
            source, len(blob), item["name"].encode("ascii"),
            ctypes.byref(found)) == R6_OK
        assert found.value == index
    assert lib.r6_enma_defaults_find(
        source, len(blob), b"R6_NO_SUCH_STRUCT",
        ctypes.byref(found)) == R6_ERR_NOT_FOUND
    absent_field = ctypes.c_uint32()
    assert lib.r6_enma_defaults_find_field(
        source, len(blob), 0, 0xFFFFFFFF,
        ctypes.byref(absent_field)) == R6_ERR_NOT_FOUND
    assert lib.r6_enma_defaults_find_field(
        source, len(blob), 32, 0,
        ctypes.byref(absent_field)) == R6_ERR_ARG

    assert lib.r6_enma_defaults_struct(source, len(blob), 32, name,
                                       len(name), None, None) == R6_ERR_ARG
    assert lib.r6_enma_defaults_field(source, len(blob), 0, 1,
                                      ctypes.byref(offset),
                                      ctypes.byref(length),
                                      payload, len(payload)) == R6_ERR_ARG
    assert lib.r6_enma_defaults_struct(source, len(blob), 0, name, 4,
                                       None, None) == R6_ERR_BUFFER
    assert lib.r6_enma_defaults_field(source, len(blob), 0, 0,
                                      ctypes.byref(offset),
                                      ctypes.byref(length),
                                      payload, 4) == R6_ERR_BUFFER
    assert lib.r6_enma_defaults_parse(source, len(blob) - 1,
                                      ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_defaults_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 31)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_defaults_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 32, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_defaults_struct(source, len(bad), 0, name, len(name),
                                       None, None) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, header.fields_off + 8, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_defaults_field(source, len(bad), 0, 0,
                                      ctypes.byref(offset),
                                      ctypes.byref(length),
                                      payload, len(payload)) == R6_ERR_FORMAT
    print("Enma defaults: all 32 structs, 89 fields and 2642 constant bytes "
          "match enma_api.json; struct/field find, bad blob, index and "
          "capacity rejected")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
