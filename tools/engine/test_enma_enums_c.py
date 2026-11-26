"""Check the C Enma enum reader against the shipped DLL export probes."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import enma_enum_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


def check(lib):
    lib.r6_enma_enum_parse.restype = ctypes.c_int
    lib.r6_enma_enum_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_enma_enum_name.restype = ctypes.c_int
    lib.r6_enma_enum_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_uint32, ctypes.c_char_p,
                                      ctypes.c_size_t]
    lib.r6_enma_enum_find_domain.restype = ctypes.c_int
    lib.r6_enma_enum_find_domain.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                             ctypes.c_char_p,
                                             ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_enma_enum_count.restype = ctypes.c_int
    lib.r6_enma_enum_count.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32,
                                       ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_enma_enum_value.restype = ctypes.c_int
    lib.r6_enma_enum_value.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.POINTER(ctypes.c_uint32),
                                       ctypes.c_char_p, ctypes.c_size_t]
    lib.r6_enma_enum_find.restype = ctypes.c_int
    lib.r6_enma_enum_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_char_p, ctypes.c_size_t]

    enums = enma_enum_catalog.collect()
    blob = enma_enum_catalog.build(enums)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_enma_enum_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert header.count == 16
    assert header.strings_off == 24 + 16 * 16 + 1214 * 8
    assert header.strings_off + header.strings_size == len(blob)

    name = ctypes.create_string_buffer(NAME_CAP)
    value = ctypes.c_uint32()
    count = ctypes.c_uint32()
    total = 0
    for index, item in enumerate(enums):
        assert lib.r6_enma_enum_name(source, len(blob), index, name,
                                     len(name)) == R6_OK
        assert name.value.decode("ascii") == item["name"]
        assert lib.r6_enma_enum_count(source, len(blob), index,
                                      ctypes.byref(count)) == R6_OK
        assert count.value == len(item["values"])
        for ordinal, (expected, symbol) in enumerate(item["values"]):
            assert lib.r6_enma_enum_value(source, len(blob), index, ordinal,
                                          ctypes.byref(value), name,
                                          len(name)) == R6_OK
            assert value.value == expected
            assert name.value.decode("ascii") == symbol
            assert lib.r6_enma_enum_find(source, len(blob), index, expected,
                                         name, len(name)) == R6_OK
            assert name.value.decode("ascii") == symbol
            total += 1
    assert total == 1214

    found = ctypes.c_uint32()
    for index, item in enumerate(enums):
        assert lib.r6_enma_enum_find_domain(
            source, len(blob), item["name"].encode("ascii"),
            ctypes.byref(found)) == R6_OK
        assert found.value == index
    assert lib.r6_enma_enum_find_domain(
        source, len(blob), b"R6_NO_SUCH_DOMAIN",
        ctypes.byref(found)) == R6_ERR_NOT_FOUND

    assert lib.r6_enma_enum_name(source, len(blob), 16, name,
                                 len(name)) == R6_ERR_ARG
    assert lib.r6_enma_enum_value(source, len(blob), 0, 304,
                                  ctypes.byref(value), name,
                                  len(name)) == R6_ERR_ARG
    assert lib.r6_enma_enum_find(source, len(blob), 0, 0xFFFFFFFF, name,
                                 len(name)) == R6_ERR_NOT_FOUND
    assert lib.r6_enma_enum_name(source, len(blob), 0, name,
                                 4) == R6_ERR_BUFFER
    assert lib.r6_enma_enum_count(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_enma_enum_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_enum_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 15)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_enum_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24 + 8, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_enum_count(source, len(bad), 0,
                                  ctypes.byref(count)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_enum_name(source, len(bad), 0, name,
                                 len(name)) == R6_ERR_FORMAT
    print("Enma enums: all 16 domains and 1214 names/values match "
          "enma_api.json; find, bad blob, index, value and capacity rejected")


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
