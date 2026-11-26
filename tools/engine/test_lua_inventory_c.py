"""Check the C Lua inventory reader against the shipped recon report."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import lua_inventory_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80

ROOT_KEYS = ("files", "bytes", "defined", "calls", "undefined",
             "native_candidates")


class Header(ctypes.Structure):
    _fields_ = [("root_count", ctypes.c_uint32),
                ("dir_count", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32),
                ("files", ctypes.c_uint32 * 2),
                ("bytes", ctypes.c_uint32 * 2),
                ("defined", ctypes.c_uint32 * 2),
                ("calls", ctypes.c_uint32 * 2),
                ("undefined", ctypes.c_uint32 * 2),
                ("native_candidates", ctypes.c_uint32 * 2)]


class Dir(ctypes.Structure):
    _fields_ = [("root", ctypes.c_uint32), ("files", ctypes.c_uint32),
                ("bytes", ctypes.c_uint32), ("with_logic", ctypes.c_uint32)]


def check(lib):
    lib.r6_lua_inventory_parse.restype = ctypes.c_int
    lib.r6_lua_inventory_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.POINTER(Header)]
    lib.r6_lua_inventory_name.restype = ctypes.c_int
    lib.r6_lua_inventory_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_uint32, ctypes.c_char_p,
                                          ctypes.c_size_t]
    lib.r6_lua_inventory_dir.restype = ctypes.c_int
    lib.r6_lua_inventory_dir.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_uint32,
                                         ctypes.POINTER(Dir)]
    lib.r6_lua_inventory_find.restype = ctypes.c_int
    lib.r6_lua_inventory_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_uint32, ctypes.c_char_p,
                                          ctypes.POINTER(ctypes.c_uint32)]

    roots, dirs = lua_inventory_catalog.collect()
    blob = lua_inventory_catalog.build(roots, dirs)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_lua_inventory_parse(source, len(blob),
                                      ctypes.byref(header)) == R6_OK
    assert header.root_count == 2 and header.dir_count == 158
    assert header.strings_size == len(blob) - (76 + 158 * 20)
    for root in range(2):
        for key in ROOT_KEYS:
            assert getattr(header, key)[root] == roots[root][key], \
                (root, key, roots[root][key])

    name = ctypes.create_string_buffer(NAME_CAP)
    row = Dir()
    index = ctypes.c_uint32()
    for ordinal, expected in enumerate(dirs):
        assert lib.r6_lua_inventory_name(source, len(blob), ordinal, name,
                                         len(name)) == R6_OK
        assert name.value.decode("ascii") == expected["dir"]
        assert lib.r6_lua_inventory_dir(source, len(blob), ordinal,
                                        ctypes.byref(row)) == R6_OK
        assert row.root == expected["root"]
        assert row.files == expected["files"]
        assert row.bytes == expected["bytes"]
        assert row.with_logic == expected["with_logic"]
        assert lib.r6_lua_inventory_find(source, len(blob), expected["root"],
                                         expected["dir"].encode("ascii"),
                                         ctypes.byref(index)) == R6_OK
        assert index.value == ordinal

    assert lib.r6_lua_inventory_name(source, len(blob), 158, name,
                                     len(name)) == R6_ERR_ARG
    assert lib.r6_lua_inventory_find(source, len(blob), 0, b"missing",
                                     ctypes.byref(index)) == R6_ERR_NOT_FOUND
    assert lib.r6_lua_inventory_find(source, len(blob), 2, b"specification",
                                     ctypes.byref(index)) == R6_ERR_ARG
    assert lib.r6_lua_inventory_find(source, len(blob), 0, None,
                                     ctypes.byref(index)) == R6_ERR_ARG
    assert lib.r6_lua_inventory_dir(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_lua_inventory_name(source, len(blob), 0, name,
                                     4) == R6_ERR_BUFFER
    assert lib.r6_lua_inventory_parse(source, len(blob) - 1,
                                      ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_inventory_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_inventory_parse(source, len(bad),
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 76 + 4, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_inventory_name(source, len(bad), 0, name,
                                     len(name)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 76, 2)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_inventory_dir(source, len(bad), 0,
                                    ctypes.byref(row)) == R6_ERR_FORMAT
    print("Lua inventory: 2 roots, 158 dirs and all root counts match "
          "lua.json; bad blob, root and capacity rejected")


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
