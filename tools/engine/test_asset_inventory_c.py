"""Check the C asset inventory reader against the shipped recon report."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import asset_inventory_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)


class Header(ctypes.Structure):
    _fields_ = [("root_count", U32),
                ("classified", U32 * 2),
                ("ext_count", U32 * 2),
                ("magic_count", U32 * 2),
                ("folder_count", U32 * 2),
                ("shader_count", U32),
                ("strings_size", U32)]


def configure(lib):
    lib.r6_asset_inventory_parse.restype = ctypes.c_int
    lib.r6_asset_inventory_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_asset_inventory_ext.restype = ctypes.c_int
    lib.r6_asset_inventory_ext.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, ctypes.c_char_p,
        ctypes.c_size_t, PU32, PU32, PU32, PU32, PU32]
    lib.r6_asset_inventory_magic.restype = ctypes.c_int
    lib.r6_asset_inventory_magic.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, ctypes.c_char_p,
        ctypes.c_size_t, PU32, PU32]
    lib.r6_asset_inventory_folder.restype = ctypes.c_int
    lib.r6_asset_inventory_folder.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, ctypes.c_char_p,
        ctypes.c_size_t, PU32, PU32, PU32, PU32]
    lib.r6_asset_inventory_find_ext.restype = ctypes.c_int
    lib.r6_asset_inventory_find_ext.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, PU32]
    lib.r6_asset_inventory_find_folder.restype = ctypes.c_int
    lib.r6_asset_inventory_find_folder.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, PU32]
    lib.r6_asset_inventory_shader.restype = ctypes.c_int
    lib.r6_asset_inventory_shader.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, ctypes.c_char_p,
        ctypes.c_size_t, PU32, ctypes.c_char_p]


def check(lib):
    configure(lib)
    roots, exts, magics, folders, shaders = \
        asset_inventory_catalog.collect()
    blob = asset_inventory_catalog.build(roots, exts, magics, folders,
                                         shaders)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_asset_inventory_parse(source, len(blob),
                                        ctypes.byref(header)) == R6_OK
    assert list(header.classified) == roots
    assert list(header.ext_count) == [19, 13]
    assert list(header.magic_count) == [4, 3]
    assert list(header.folder_count) == [14, 13]
    assert header.shader_count == 40
    assert header.strings_size == len(blob) - (
        60 + 32 * 48 + 7 * 12 + 27 * 20 + 40 * 24)

    name = ctypes.create_string_buffer(NAME_CAP)
    root = U32()
    files = U32()
    lo = U32()
    hi = U32()
    count = U32()
    kinds = (U32 * 7)()
    for index, expected in enumerate(exts):
        assert lib.r6_asset_inventory_ext(
            source, len(blob), index, name, len(name), ctypes.byref(root),
            ctypes.byref(files), ctypes.byref(lo), ctypes.byref(hi),
            kinds) == R6_OK
        assert root.value == expected["root"]
        assert name.value.decode("ascii") == expected["name"]
        assert files.value == expected["files"]
        assert lo.value | (hi.value << 32) == expected["bytes"]
        assert list(kinds) == expected["kinds"]

    for index, expected in enumerate(magics):
        assert lib.r6_asset_inventory_magic(
            source, len(blob), index, name, len(name), ctypes.byref(root),
            ctypes.byref(count)) == R6_OK
        assert root.value == expected["root"]
        assert name.value.decode("ascii") == expected["name"]
        assert count.value == expected["count"]

    for index, expected in enumerate(folders):
        assert lib.r6_asset_inventory_folder(
            source, len(blob), index, name, len(name), ctypes.byref(root),
            ctypes.byref(files), ctypes.byref(lo),
            ctypes.byref(hi)) == R6_OK
        assert root.value == expected["root"]
        assert name.value.decode("ascii") == expected["name"]
        assert files.value == expected["files"]
        assert lo.value | (hi.value << 32) == expected["bytes"]

    head = ctypes.create_string_buffer(16)
    for index, expected in enumerate(shaders):
        assert lib.r6_asset_inventory_shader(
            source, len(blob), index, name, len(name), ctypes.byref(count),
            head) == R6_OK
        assert name.value.decode("ascii") == expected["path"]
        assert count.value == expected["size"]
        assert head.raw[:16] == expected["head"]

    found = U32()
    assert lib.r6_asset_inventory_find_ext(
        source, len(blob), exts[0]["name"].encode("ascii"),
        ctypes.byref(found)) == R6_OK
    assert found.value == 0
    assert lib.r6_asset_inventory_find_folder(
        source, len(blob), folders[0]["name"].encode("ascii"),
        ctypes.byref(found)) == R6_OK
    assert found.value == 0
    assert lib.r6_asset_inventory_find_ext(
        source, len(blob), b"R6_NO_SUCH_EXT",
        ctypes.byref(found)) == R6_ERR_NOT_FOUND

    assert lib.r6_asset_inventory_ext(
        source, len(blob), 32, name, len(name), ctypes.byref(root),
        ctypes.byref(files), ctypes.byref(lo), ctypes.byref(hi),
        kinds) == R6_ERR_ARG
    assert lib.r6_asset_inventory_magic(
        source, len(blob), 7, name, len(name), ctypes.byref(root),
        ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_asset_inventory_folder(
        source, len(blob), 27, name, len(name), ctypes.byref(root),
        ctypes.byref(files), ctypes.byref(lo),
        ctypes.byref(hi)) == R6_ERR_ARG
    assert lib.r6_asset_inventory_shader(
        source, len(blob), 40, name, len(name), ctypes.byref(count),
        head) == R6_ERR_ARG
    assert lib.r6_asset_inventory_ext(
        source, len(blob), 0, name, 4, ctypes.byref(root),
        ctypes.byref(files), ctypes.byref(lo), ctypes.byref(hi),
        kinds) == R6_ERR_BUFFER
    assert lib.r6_asset_inventory_parse(source, len(blob) - 1,
                                        ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_asset_inventory_parse(source, len(bad),
                                        ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 18)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_asset_inventory_parse(source, len(bad),
                                        ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 60, 2)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_asset_inventory_ext(
        source, len(bad), 0, name, len(name), ctypes.byref(root),
        ctypes.byref(files), ctypes.byref(lo), ctypes.byref(hi),
        kinds) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 60 + 4, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_asset_inventory_ext(
        source, len(bad), 0, name, len(name), ctypes.byref(root),
        ctypes.byref(files), ctypes.byref(lo), ctypes.byref(hi),
        kinds) == R6_ERR_FORMAT
    print("asset inventory: 2 roots, 32 extensions, 7 magics, 27 folders "
          "and 40 shader samples match assets.json; find, bad blob, index "
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
