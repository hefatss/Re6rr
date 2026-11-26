"""Check the C Lua reference reader against the shipped xref bindings."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import lua_xref_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


class Row(ctypes.Structure):
    _fields_ = [("via", ctypes.c_uint32), ("func_count", ctypes.c_uint32),
                ("table_count", ctypes.c_uint32)]


def check(lib):
    lib.r6_lua_xref_parse.restype = ctypes.c_int
    lib.r6_lua_xref_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(Header)]
    lib.r6_lua_xref_row.restype = ctypes.c_int
    lib.r6_lua_xref_row.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.c_uint32, ctypes.POINTER(Row)]
    lib.r6_lua_xref_name.restype = ctypes.c_int
    lib.r6_lua_xref_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_uint32, ctypes.c_char_p,
                                     ctypes.c_size_t]
    lib.r6_lua_xref_func.restype = ctypes.c_int
    lib.r6_lua_xref_func.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_uint32, ctypes.c_uint32,
                                     ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_lua_xref_table.restype = ctypes.c_int
    lib.r6_lua_xref_table.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_lua_xref_user.restype = ctypes.c_int
    lib.r6_lua_xref_user.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_uint32, ctypes.c_uint32,
                                     ctypes.c_uint32,
                                     ctypes.POINTER(ctypes.c_uint32)]

    rows = lua_xref_catalog.collect()
    blob = lua_xref_catalog.build(rows)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_lua_xref_parse(source, len(blob),
                                 ctypes.byref(header)) == R6_OK
    assert header.count == 219
    array_bytes = (sum(len(row["funcs"]) * 4 for row in rows) +
                   sum(16 + len(table["users"]) * 4
                       for row in rows for table in row["tables"]))
    assert header.strings_off == 24 + 219 * 24 + array_bytes

    name = ctypes.create_string_buffer(NAME_CAP)
    row = Row()
    value = ctypes.c_uint32()
    kind = ctypes.c_uint32()
    count = ctypes.c_uint32()
    funcs = 0
    tables = 0
    users = 0
    for index, want in enumerate(rows):
        assert lib.r6_lua_xref_name(source, len(blob), index, name,
                                    len(name)) == R6_OK
        assert name.value.decode("ascii") == want["name"]
        assert lib.r6_lua_xref_row(source, len(blob), index,
                                   ctypes.byref(row)) == R6_OK
        assert row.via == want["via"]
        assert row.func_count == len(want["funcs"])
        assert row.table_count == len(want["tables"])
        for at, func in enumerate(want["funcs"]):
            assert lib.r6_lua_xref_func(source, len(blob), index, at,
                                        ctypes.byref(value)) == R6_OK
            assert value.value == func
            funcs += 1
        for at, table in enumerate(want["tables"]):
            assert lib.r6_lua_xref_table(source, len(blob), index, at,
                                         ctypes.byref(value),
                                         ctypes.byref(kind),
                                         ctypes.byref(count)) == R6_OK
            assert value.value == table["rva"]
            assert kind.value == table["kind"]
            assert count.value == len(table["users"])
            for user, expected in enumerate(table["users"]):
                assert lib.r6_lua_xref_user(source, len(blob), index, at,
                                            user, ctypes.byref(value)) == R6_OK
                assert value.value == expected
                users += 1
            tables += 1
    assert (funcs, tables) == (222, 28)

    first = rows[0]
    assert first["funcs"]
    assert lib.r6_lua_xref_func(source, len(blob), 0, len(first["funcs"]),
                                ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_lua_xref_user(source, len(blob), 0, 0, 0,
                                ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_lua_xref_name(source, len(blob), 219, name,
                                len(name)) == R6_ERR_ARG
    assert lib.r6_lua_xref_name(source, len(blob), 0, name, 4) == R6_ERR_BUFFER
    assert lib.r6_lua_xref_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_lua_xref_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_xref_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 218)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_xref_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24 + 12, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_xref_row(source, len(bad), 0,
                               ctypes.byref(row)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_xref_name(source, len(bad), 0, name,
                                len(name)) == R6_ERR_FORMAT
    print("lua xrefs: 219 names, 222 function refs, 28 table refs and %d "
          "table users match bindings.json; bad blob, index and capacity "
          "rejected" % users)


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
