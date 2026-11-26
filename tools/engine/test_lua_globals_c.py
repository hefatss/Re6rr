"""Check the C Lua global inventory reader against the shipped recon report."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import lua_globals_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6


class Header(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


def check(lib):
    lib.r6_lua_globals_parse.restype = ctypes.c_int
    lib.r6_lua_globals_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(Header)]
    lib.r6_lua_globals_row.restype = ctypes.c_int
    lib.r6_lua_globals_row.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32, ctypes.c_char_p,
                                       ctypes.c_size_t, ctypes.POINTER(
                                           ctypes.c_uint32),
                                       ctypes.POINTER(ctypes.c_uint32)]

    categories, rows = lua_globals_catalog.collect()
    blob = lua_globals_catalog.build(categories, rows)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_lua_globals_parse(source, len(blob),
                                    ctypes.byref(header)) == R6_OK
    assert header.count == 219
    assert header.strings_off == 24 + 219 * 12
    assert header.strings_off + header.strings_size == len(blob)

    name = ctypes.create_string_buffer(0x80)
    calls = ctypes.c_uint32()
    category = ctypes.c_uint32()
    for index, row in enumerate(rows):
        assert lib.r6_lua_globals_row(source, len(blob), index, name,
                                      len(name), ctypes.byref(calls),
                                      ctypes.byref(category)) == R6_OK
        assert name.value.decode("ascii") == row["name"], index
        assert calls.value == row["calls"], index
        assert category.value == row["category"], index

    assert lib.r6_lua_globals_row(source, len(blob), 219, name, len(name),
                                  None, None) == R6_ERR_ARG
    assert lib.r6_lua_globals_row(source, len(blob), 0, name, 4,
                                  None, None) == R6_ERR_BUFFER
    assert lib.r6_lua_globals_parse(source, len(blob) - 1,
                                    ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_globals_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 218)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_globals_parse(source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_globals_row(source, len(bad), 0, name, len(name),
                                  None, None) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 32, 7)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_globals_row(source, len(bad), 0, name, len(name),
                                  None, None) == R6_ERR_FORMAT
    assert lib.r6_lua_globals_row(source, len(bad), 0, None, len(name),
                                  None, None) == R6_ERR_ARG
    assert lib.r6_lua_globals_parse(None, len(blob),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    print("lua globals: all 219 shipped names, call counts and 7 categories "
          "match LUA_API.md; bad blob, index and capacity rejected")


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
