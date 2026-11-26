"""Check the C raw string-xref reader against xrefs.json."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import string_xrefs_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
NAME_OFF = 48
RVA_OFF = NAME_OFF + 195 * 12
STRINGS_OFF = RVA_OFF + 222 * 4

FIELDS = ("version", "instructions", "string_refs", "strings",
          "names_requested", "names_found", "name_count", "rva_count",
          "strings_size", "strings_off")


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_string_xref_parse.restype = ctypes.c_int
    lib.r6_string_xref_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_string_xref_name.restype = ctypes.c_int
    lib.r6_string_xref_name.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t, PU32,
        PU32]
    lib.r6_string_xref_rva.restype = ctypes.c_int
    lib.r6_string_xref_rva.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32]
    lib.r6_string_xref_name_rva.restype = ctypes.c_int
    lib.r6_string_xref_name_rva.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, U32, PU32]
    lib.r6_string_xref_find.restype = ctypes.c_int
    lib.r6_string_xref_find.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, PU32]


def check(lib):
    configure(lib)
    data = string_xrefs_catalog.collect()
    blob = string_xrefs_catalog.build(data)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_string_xref_parse(source, len(blob),
                                    ctypes.byref(header)) == R6_OK
    expected = (1, data["instructions"], data["string_refs"],
                data["strings"], data["names_requested"],
                data["names_found"], len(data["hits"]), 222)
    assert tuple(getattr(header, field) for field in FIELDS[:8]) == expected
    assert header.strings_off == STRINGS_OFF
    assert header.strings_size == len(blob) - STRINGS_OFF

    name = ctypes.create_string_buffer(256)
    first = U32()
    count = U32()
    firsts = []
    expected_first = 0
    for index, (expected_name, refs) in enumerate(data["hits"].items()):
        assert lib.r6_string_xref_name(
            source, len(blob), index, name, len(name), ctypes.byref(first),
            ctypes.byref(count)) == R6_OK
        assert name.value.decode("ascii") == expected_name
        assert first.value == expected_first
        assert count.value == len(refs)
        firsts.append(expected_first)
        expected_first += len(refs)
    assert expected_first == 222

    rva = U32()
    for index, refs in enumerate(data["hits"].values()):
        for local, expected_rva in enumerate(refs):
            assert lib.r6_string_xref_rva(
                source, len(blob), firsts[index] + local,
                ctypes.byref(rva)) == R6_OK
            assert rva.value == expected_rva
            assert lib.r6_string_xref_name_rva(
                source, len(blob), index, local,
                ctypes.byref(rva)) == R6_OK
            assert rva.value == expected_rva

    found = U32()
    first_name = next(iter(data["hits"]))
    assert lib.r6_string_xref_find(
        source, len(blob), first_name.encode("ascii"),
        ctypes.byref(found)) == R6_OK
    assert found.value == 0
    assert lib.r6_string_xref_find(
        source, len(blob), b"R6_NO_SUCH_XREF",
        ctypes.byref(found)) == R6_ERR_NOT_FOUND

    assert lib.r6_string_xref_name(
        source, len(blob), 195, name, len(name), ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_string_xref_rva(
        source, len(blob), 222, ctypes.byref(rva)) == R6_ERR_ARG
    assert lib.r6_string_xref_name_rva(
        source, len(blob), 0, len(next(iter(data["hits"].values()))),
        ctypes.byref(rva)) == R6_ERR_ARG
    assert lib.r6_string_xref_name(
        source, len(blob), 0, name, 4, ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_BUFFER
    assert lib.r6_string_xref_parse(source, len(blob) - 1,
                                    ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_string_xref_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, NAME_OFF + 4, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_string_xref_name(
        source, len(bad), 0, name, len(name), ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, NAME_OFF + 12 + 4, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_string_xref_name(
        source, len(bad), 1, name, len(name), ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, RVA_OFF, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_string_xref_rva(
        source, len(bad), 0, ctypes.byref(rva)) == R6_ERR_FORMAT
    print("string xrefs: 195 names, 222 RVAs and scan totals match "
          "xrefs.json; find, bad blob, index, row and capacity rejected")


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
