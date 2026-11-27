"""Check the C luaL_Reg reader against name_tables.json."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import lua_reg_tables_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
TABLE_OFF = 28
ENTRY_OFF = TABLE_OFF + 3 * 28


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in
                ("version", "table_count", "entry_count", "user_count",
                 "strings_size")]


def configure(lib):
    lib.r6_lua_reg_parse.restype = ctypes.c_int
    lib.r6_lua_reg_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_lua_reg_table.restype = ctypes.c_int
    lib.r6_lua_reg_table.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32, PU32, PU32,
        PU32, PU32, PU32]
    lib.r6_lua_reg_entry.restype = ctypes.c_int
    lib.r6_lua_reg_entry.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t, PU32]
    lib.r6_lua_reg_table_entry.restype = ctypes.c_int
    lib.r6_lua_reg_table_entry.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, U32, BUF, ctypes.c_size_t,
        PU32]
    lib.r6_lua_reg_user.restype = ctypes.c_int
    lib.r6_lua_reg_user.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32]
    lib.r6_lua_reg_find.restype = ctypes.c_int
    lib.r6_lua_reg_find.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, PU32, PU32, PU32]
    lib.r6_lua_reg_find_rva.restype = ctypes.c_int
    lib.r6_lua_reg_find_rva.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, U32, PU32]


def check(lib):
    configure(lib)
    tables, entries, users = lua_reg_tables_catalog.collect()
    blob = lua_reg_tables_catalog.build(tables, entries, users)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_lua_reg_parse(source, len(blob),
                                ctypes.byref(header)) == R6_OK
    assert header.version == 1
    assert header.table_count == 3
    assert header.entry_count == 42
    assert header.user_count == 1

    rva = U32()
    size = U32()
    stride = U32()
    count = U32()
    first_entry = U32()
    first_user = U32()
    user_count = U32()
    expected_entry = 0
    expected_user = 0
    for index, table in enumerate(tables):
        assert lib.r6_lua_reg_table(
            source, len(blob), index, ctypes.byref(rva), ctypes.byref(size),
            ctypes.byref(stride), ctypes.byref(count),
            ctypes.byref(first_entry), ctypes.byref(first_user),
            ctypes.byref(user_count)) == R6_OK
        assert rva.value == table["rva"]
        assert size.value == table["size"]
        assert stride.value == table["stride"]
        assert count.value == table["count"]
        assert first_entry.value == expected_entry
        assert first_user.value == expected_user
        assert user_count.value == len(table["users"])
        expected_entry += table["count"]
        expected_user += len(table["users"])

    out = ctypes.create_string_buffer(256)
    for index, expected in enumerate(entries):
        assert lib.r6_lua_reg_entry(
            source, len(blob), index, out, len(out),
            ctypes.byref(rva)) == R6_OK
        assert out.value.decode("ascii") == expected[0]
        assert rva.value == expected[1]

    for table_index, table in enumerate(tables):
        for local_index, expected in enumerate(table["entries"]):
            assert lib.r6_lua_reg_table_entry(
                source, len(blob), table_index, local_index, out, len(out),
                ctypes.byref(rva)) == R6_OK
            assert out.value.decode("ascii") == expected[0]
            assert rva.value == expected[1]

    for index, expected in enumerate(users):
        assert lib.r6_lua_reg_user(
            source, len(blob), index, ctypes.byref(rva)) == R6_OK
        assert rva.value == expected

    table = U32()
    local = U32()
    global_index = U32()
    assert lib.r6_lua_reg_find(
        source, len(blob), b"PlaySE", ctypes.byref(table),
        ctypes.byref(local), ctypes.byref(global_index)) == R6_OK
    assert (table.value, local.value, global_index.value) == (1, 0, 27)
    assert lib.r6_lua_reg_find(
        source, len(blob), b"@SVWH", ctypes.byref(table),
        ctypes.byref(local), ctypes.byref(global_index)) == R6_OK
    assert (table.value, local.value, global_index.value) == (0, 0, 0)
    assert lib.r6_lua_reg_find(
        source, len(blob), b"R6_NO_SUCH_NAME", ctypes.byref(table),
        ctypes.byref(local), ctypes.byref(global_index)) == R6_ERR_NOT_FOUND

    by_rva = {}
    for index, expected in enumerate(entries):
        by_rva.setdefault(expected[1], []).append(index)
    total = U32()
    for value, want in by_rva.items():
        hits = (U32 * len(want))()
        assert lib.r6_lua_reg_find_rva(
            source, len(blob), value, hits, len(hits),
            ctypes.byref(total)) == R6_OK
        assert total.value == len(want) and list(hits) == want
    assert lib.r6_lua_reg_find_rva(
        source, len(blob), 0x1000, None, 0,
        ctypes.byref(total)) == R6_ERR_NOT_FOUND
    assert total.value == 0
    for bad_rva in (0xfff, 34308096):
        assert lib.r6_lua_reg_find_rva(
            source, len(blob), bad_rva, None, 0,
            ctypes.byref(total)) == R6_ERR_ARG
    assert lib.r6_lua_reg_find_rva(
        source, len(blob), entries[0][1], None, 1,
        ctypes.byref(total)) == R6_ERR_ARG

    duplicate = bytearray(blob)
    struct.pack_into("<I", duplicate, ENTRY_OFF + 8 + 4, entries[0][1])
    source = ctypes.create_string_buffer(bytes(duplicate), len(duplicate))
    short = (U32 * 1)()
    assert lib.r6_lua_reg_find_rva(
        source, len(duplicate), entries[0][1], short, len(short),
        ctypes.byref(total)) == R6_ERR_BUFFER
    assert total.value == 2 and list(short) == [0]
    source = ctypes.create_string_buffer(blob, len(blob))

    assert lib.r6_lua_reg_table(
        source, len(blob), 3, ctypes.byref(rva), ctypes.byref(size),
        ctypes.byref(stride), ctypes.byref(count), ctypes.byref(first_entry),
        ctypes.byref(first_user), ctypes.byref(user_count)) == R6_ERR_ARG
    assert lib.r6_lua_reg_entry(
        source, len(blob), 42, out, len(out),
        ctypes.byref(rva)) == R6_ERR_ARG
    assert lib.r6_lua_reg_user(
        source, len(blob), 1, ctypes.byref(rva)) == R6_ERR_ARG
    assert lib.r6_lua_reg_entry(
        source, len(blob), 0, out, 4, ctypes.byref(rva)) == R6_ERR_BUFFER
    assert lib.r6_lua_reg_parse(source, len(blob) - 1,
                                ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_reg_parse(source, len(bad),
                                ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, TABLE_OFF + 4, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_lua_reg_table(
        source, len(bad), 0, ctypes.byref(rva), ctypes.byref(size),
        ctypes.byref(stride), ctypes.byref(count), ctypes.byref(first_entry),
        ctypes.byref(first_user), ctypes.byref(user_count)) == R6_ERR_FORMAT
    print("luaL_Reg tables: 3 tables, 42 entries and one code ref match "
          "name_tables.json; both find directions, bad blob, index, row, RVA "
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
