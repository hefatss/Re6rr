"""Check the C path-string reader against the shipped recon reports."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import path_strings_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
GROUP_OFF = 24
WORD_OFF = GROUP_OFF + 2 * 12
STRING_OFF = WORD_OFF + 1693 * 4


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in
                ("version", "group_count", "string_count", "strings_size")]


def configure(lib):
    lib.r6_path_strings_parse.restype = ctypes.c_int
    lib.r6_path_strings_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_path_strings_group.restype = ctypes.c_int
    lib.r6_path_strings_group.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32, PU32]
    lib.r6_path_strings_get.restype = ctypes.c_int
    lib.r6_path_strings_get.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]
    lib.r6_path_strings_group_get.restype = ctypes.c_int
    lib.r6_path_strings_group_get.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, U32, BUF, ctypes.c_size_t]
    lib.r6_path_strings_find.restype = ctypes.c_int
    lib.r6_path_strings_find.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, PU32, PU32, PU32]


def check(lib):
    configure(lib)
    groups = path_strings_catalog.collect()
    blob = path_strings_catalog.build(groups)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_path_strings_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert header.version == 1
    assert header.group_count == 2
    assert header.string_count == 1693
    assert header.strings_size == len(blob) - STRING_OFF

    kind = U32()
    count = U32()
    first = U32()
    expected_first = 0
    for index, group in enumerate(groups):
        assert lib.r6_path_strings_group(
            source, len(blob), index, ctypes.byref(kind), ctypes.byref(count),
            ctypes.byref(first)) == R6_OK
        assert kind.value == index
        assert count.value == (1271 if index == 0 else 422)
        assert first.value == expected_first
        expected_first += count.value

    out = ctypes.create_string_buffer(256)
    for index, expected in enumerate(groups[0] + groups[1]):
        assert lib.r6_path_strings_get(
            source, len(blob), index, out, len(out)) == R6_OK
        assert out.value.decode("ascii") == expected

    for group_index, group in enumerate(groups):
        for local_index, expected in enumerate(group):
            assert lib.r6_path_strings_group_get(
                source, len(blob), group_index, local_index, out,
                len(out)) == R6_OK
            assert out.value.decode("ascii") == expected

    group = U32()
    local = U32()
    global_index = U32()
    assert lib.r6_path_strings_find(
        source, len(blob), b"course viewer", ctypes.byref(group),
        ctypes.byref(local), ctypes.byref(global_index)) == R6_OK
    assert (group.value, local.value, global_index.value) == (0, 0, 0)
    assert lib.r6_path_strings_find(
        source, len(blob), groups[1][0].encode("ascii"), ctypes.byref(group),
        ctypes.byref(local), ctypes.byref(global_index)) == R6_OK
    assert (group.value, local.value, global_index.value) == (1, 0, 1271)
    assert lib.r6_path_strings_find(
        source, len(blob), b"R6_NO_SUCH_PATH", ctypes.byref(group),
        ctypes.byref(local), ctypes.byref(global_index)) == R6_ERR_NOT_FOUND

    assert lib.r6_path_strings_group(
        source, len(blob), 2, ctypes.byref(kind), ctypes.byref(count),
        ctypes.byref(first)) == R6_ERR_ARG
    assert lib.r6_path_strings_get(
        source, len(blob), 1693, out, len(out)) == R6_ERR_ARG
    assert lib.r6_path_strings_get(
        source, len(blob), 0, out, 4) == R6_ERR_BUFFER
    assert lib.r6_path_strings_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_path_strings_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, GROUP_OFF + 4, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_path_strings_group(
        source, len(bad), 0, ctypes.byref(kind), ctypes.byref(count),
        ctypes.byref(first)) == R6_ERR_FORMAT
    print("path strings: 1271 executable and 422 source strings match "
          "exe_paths.json/source_paths.json; find, bad blob, index, group "
          "and capacity rejected")


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
