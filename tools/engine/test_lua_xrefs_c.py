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
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


class Row(ctypes.Structure):
    _fields_ = [("via", ctypes.c_uint32), ("func_count", ctypes.c_uint32),
                ("table_count", ctypes.c_uint32)]


class Hit(ctypes.Structure):
    _fields_ = [("row", ctypes.c_uint32), ("kind", ctypes.c_uint32),
                ("which", ctypes.c_uint32), ("item", ctypes.c_uint32)]


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
    lib.r6_lua_xref_find.restype = ctypes.c_int
    lib.r6_lua_xref_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_char_p,
                                     ctypes.POINTER(ctypes.c_uint32)]
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
    lib.r6_lua_xref_find_rva.restype = ctypes.c_int
    lib.r6_lua_xref_find_rva.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_uint32, ctypes.POINTER(Hit),
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

    found = ctypes.c_uint32()
    for index, want in enumerate(rows):
        assert lib.r6_lua_xref_find(
            source, len(blob), want["name"].encode("ascii"),
            ctypes.byref(found)) == R6_OK
        assert found.value == index
    assert lib.r6_lua_xref_find(
        source, len(blob), b"R6_NO_SUCH_XREF_NAME",
        ctypes.byref(found)) == R6_ERR_NOT_FOUND

    reverse = {}
    for row_index, want in enumerate(rows):
        for at, func in enumerate(want["funcs"]):
            reverse.setdefault(func, []).append((row_index, 0, at, 0))
        for which, table in enumerate(want["tables"]):
            reverse.setdefault(table["rva"], []).append(
                (row_index, 1, which, 0))
            for item, user in enumerate(table["users"]):
                reverse.setdefault(user, []).append(
                    (row_index, 2, which, item))
    total = ctypes.c_uint32()
    duplicates = 0
    for expected_rva, want in reverse.items():
        hits = (Hit * len(want))()
        assert lib.r6_lua_xref_find_rva(
            source, len(blob), expected_rva, hits, len(hits),
            ctypes.byref(total)) == R6_OK
        assert total.value == len(want)
        assert [(hit.row, hit.kind, hit.which, hit.item) for hit in hits] == want
        if len(want) > 1:
            duplicates += 1
    assert duplicates
    absent = 0x1000
    while absent in reverse:
        absent += 1
    assert lib.r6_lua_xref_find_rva(
        source, len(blob), absent, None, 0,
        ctypes.byref(total)) == R6_ERR_NOT_FOUND and total.value == 0
    for bad_rva in (0xfff, 34308096):
        assert lib.r6_lua_xref_find_rva(
            source, len(blob), bad_rva, None, 0,
            ctypes.byref(total)) == R6_ERR_ARG
    first_rva = next(iter(reverse))
    assert lib.r6_lua_xref_find_rva(
        source, len(blob), first_rva, None, 1,
        ctypes.byref(total)) == R6_ERR_ARG
    assert lib.r6_lua_xref_find_rva(
        source, len(blob), first_rva, None, 0, None) == R6_ERR_BUFFER

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
    print("lua xrefs: 219 names, 222 function refs, 28 table refs, %d table "
          "users and %d duplicate-RVA groups match bindings.json; both find "
          "directions, bad blob, index and capacity rejected" %
          (users, duplicates))


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
