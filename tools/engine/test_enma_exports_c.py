"""Check the C Enma export reader against the shipped DLL export table."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import enma_exports_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


def check(lib):
    lib.r6_enma_exports_parse.restype = ctypes.c_int
    lib.r6_enma_exports_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_enma_exports_name.restype = ctypes.c_int
    lib.r6_enma_exports_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_uint32, ctypes.c_char_p,
                                         ctypes.c_size_t]
    lib.r6_enma_exports_find.restype = ctypes.c_int
    lib.r6_enma_exports_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_char_p,
                                         ctypes.POINTER(ctypes.c_uint32)]

    names = enma_exports_catalog.collect()
    blob = enma_exports_catalog.build(names)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_enma_exports_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert header.count == 172
    assert header.strings_off == 24 + 172 * 4
    assert header.strings_off + header.strings_size == len(blob)

    name = ctypes.create_string_buffer(NAME_CAP)
    index = ctypes.c_uint32()
    for ordinal, expected in enumerate(names):
        assert lib.r6_enma_exports_name(source, len(blob), ordinal, name,
                                        len(name)) == R6_OK
        assert name.value.decode("ascii") == expected
        assert lib.r6_enma_exports_find(source, len(blob),
                                        expected.encode("ascii"),
                                        ctypes.byref(index)) == R6_OK
        assert index.value == ordinal

    assert lib.r6_enma_exports_name(source, len(blob), 172, name,
                                    len(name)) == R6_ERR_ARG
    assert lib.r6_enma_exports_find(source, len(blob), b"missing",
                                    ctypes.byref(index)) == R6_ERR_NOT_FOUND
    assert lib.r6_enma_exports_find(source, len(blob), None,
                                    ctypes.byref(index)) == R6_ERR_ARG
    assert lib.r6_enma_exports_find(source, len(blob), b"x",
                                    None) == R6_ERR_ARG
    assert lib.r6_enma_exports_name(source, len(blob), 0, name,
                                    4) == R6_ERR_BUFFER
    assert lib.r6_enma_exports_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_exports_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 171)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_exports_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_exports_name(source, len(bad), 0, name,
                                    len(name)) == R6_ERR_FORMAT
    print("Enma exports: all 172 mangled names and ordinals match "
          "enma_api.json; bad blob, index and capacity rejected")


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
