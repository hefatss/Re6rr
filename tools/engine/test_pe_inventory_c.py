"""Check the C PE inventory reader against the shipped recon reports."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import pe_inventory_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
FUNC_OFF = 120
DLL_OFF = FUNC_OFF + 70377 * 16


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in (
        "version", "file_size", "machine", "pe_magic", "timestamp",
        "image_base_lo", "image_base_hi", "entry_rva", "size_of_image",
        "directory_count", "pdata_count", "unique_unwind", "code_bytes",
        "text_bytes", "leaf", "chained", "with_eh", "reloc_blocks",
        "reloc_entries", "dll_count", "import_count", "export_count",
        "tls_count", "section_count", "strings_size", "guid_off", "pdb_age",
        "path_off")]


def configure(lib):
    lib.r6_pe_inventory_parse.restype = ctypes.c_int
    lib.r6_pe_inventory_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_pe_inventory_func.restype = ctypes.c_int
    lib.r6_pe_inventory_func.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32, PU32, PU32]
    lib.r6_pe_inventory_dll.restype = ctypes.c_int
    lib.r6_pe_inventory_dll.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t,
        PU32, PU32]
    lib.r6_pe_inventory_import.restype = ctypes.c_int
    lib.r6_pe_inventory_import.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32, BUF,
        ctypes.c_size_t]
    lib.r6_pe_inventory_section.restype = ctypes.c_int
    lib.r6_pe_inventory_section.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t,
        PU32, PU32, PU32, PU32, PU32]
    lib.r6_pe_inventory_export.restype = ctypes.c_int
    lib.r6_pe_inventory_export.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]
    lib.r6_pe_inventory_tls.restype = ctypes.c_int
    lib.r6_pe_inventory_tls.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32]
    lib.r6_pe_inventory_pdb.restype = ctypes.c_int
    lib.r6_pe_inventory_pdb.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, BUF, ctypes.c_size_t, PU32, BUF,
        ctypes.c_size_t]


def check(lib):
    configure(lib)
    pe, pdata, funcs = pe_inventory_catalog.collect()
    blob = pe_inventory_catalog.build(pe, pdata, funcs)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_pe_inventory_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert header.version == 1
    assert header.file_size == pe["size"]
    assert header.machine == int(pe["machine"], 16)
    assert header.pe_magic == int(pe["magic"], 16)
    assert header.timestamp == pe["timestamp"]
    assert header.image_base_lo == 0x40000000
    assert header.image_base_hi == 1
    assert header.entry_rva == int(pe["entry_rva"], 16)
    assert header.size_of_image == pe["size_of_image"]
    assert header.directory_count == len(pe["directories"])
    assert header.pdata_count == 70377
    assert header.unique_unwind == pe["pdata"]["unique_unwind"]
    assert header.code_bytes == pdata["code_bytes"]
    assert header.text_bytes == pdata["text_bytes"]
    assert header.leaf == pdata["leaf"]
    assert header.chained == pdata["chained"]
    assert header.with_eh == pdata["with_eh"]
    assert header.reloc_blocks == pe["relocations"]["blocks"]
    assert header.reloc_entries == pe["relocations"]["entries"]
    assert header.dll_count == 28 and header.import_count == 825
    assert header.export_count == len(pe["exports"])
    assert header.tls_count == len(pe["tls"]["callbacks"])
    assert header.section_count == len(pe["sections"])
    assert header.pdb_age == pe["debug"]["pdb"]["age"]

    rva = U32()
    end = U32()
    length = U32()
    leaf = U32()
    for index, expected in enumerate(funcs):
        assert lib.r6_pe_inventory_func(
            source, len(blob), index, ctypes.byref(rva), ctypes.byref(end),
            ctypes.byref(length), ctypes.byref(leaf)) == R6_OK
        assert rva.value == expected["rva"]
        assert end.value == expected["end"]
        assert length.value == expected["size"]
        assert leaf.value == (1 if expected["leaf"] else 0)

    name = ctypes.create_string_buffer(256)
    first = U32()
    count = U32()
    imports = []
    total = 0
    for index, item in enumerate(pe["imports"]):
        assert lib.r6_pe_inventory_dll(
            source, len(blob), index, name, len(name), ctypes.byref(first),
            ctypes.byref(count)) == R6_OK
        assert name.value.decode("ascii") == item["dll"]
        assert first.value == total
        assert count.value == len(item["functions"])
        total += count.value
        imports.extend(item["functions"])
    assert total == 825

    kind = U32()
    ordinal = U32()
    for index, expected in enumerate(imports):
        assert lib.r6_pe_inventory_import(
            source, len(blob), index, ctypes.byref(kind),
            ctypes.byref(ordinal), name, len(name)) == R6_OK
        if "ordinal" in expected:
            assert kind.value == 1 and ordinal.value == expected["ordinal"]
            assert name.value == b""
        else:
            assert kind.value == 0 and ordinal.value == 0
            assert name.value.decode("ascii") == expected["name"]

    vsize = U32()
    vaddr = U32()
    raw_size = U32()
    raw_ptr = U32()
    characteristics = U32()
    for index, expected in enumerate(pe["sections"]):
        assert lib.r6_pe_inventory_section(
            source, len(blob), index, name, len(name), ctypes.byref(vsize),
            ctypes.byref(vaddr), ctypes.byref(raw_size),
            ctypes.byref(raw_ptr), ctypes.byref(characteristics)) == R6_OK
        assert name.value.decode("ascii") == expected["name"]
        assert vsize.value == expected["vsize"]
        assert vaddr.value == expected["vaddr"]
        assert raw_size.value == expected["raw_size"]
        assert raw_ptr.value == expected["raw_ptr"]
        assert characteristics.value == expected["characteristics"]

    for index, expected in enumerate(pe["exports"]):
        assert lib.r6_pe_inventory_export(
            source, len(blob), index, name, len(name)) == R6_OK
        assert name.value.decode("ascii") == expected

    lo = U32()
    hi = U32()
    for index, expected in enumerate(pe["tls"]["callbacks"]):
        assert lib.r6_pe_inventory_tls(
            source, len(blob), index, ctypes.byref(lo),
            ctypes.byref(hi)) == R6_OK
        assert (lo.value | (hi.value << 32)) == int(expected, 16)

    guid = ctypes.create_string_buffer(64)
    path = ctypes.create_string_buffer(512)
    assert lib.r6_pe_inventory_pdb(
        source, len(blob), guid, len(guid), ctypes.byref(ordinal), path,
        len(path)) == R6_OK
    assert guid.value.decode("ascii") == pe["debug"]["pdb"]["guid"]
    assert ordinal.value == pe["debug"]["pdb"]["age"]
    assert path.value.decode("ascii") == pe["debug"]["pdb"]["path"]

    assert lib.r6_pe_inventory_func(
        source, len(blob), 70377, ctypes.byref(rva), ctypes.byref(end),
        ctypes.byref(length), ctypes.byref(leaf)) == R6_ERR_ARG
    assert lib.r6_pe_inventory_dll(
        source, len(blob), 28, name, len(name), ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_pe_inventory_import(
        source, len(blob), 825, ctypes.byref(kind), ctypes.byref(ordinal),
        name, len(name)) == R6_ERR_ARG
    assert lib.r6_pe_inventory_section(
        source, len(blob), 7, name, len(name), ctypes.byref(vsize),
        ctypes.byref(vaddr), ctypes.byref(raw_size), ctypes.byref(raw_ptr),
        ctypes.byref(characteristics)) == R6_ERR_ARG
    assert lib.r6_pe_inventory_export(
        source, len(blob), 2, name, len(name)) == R6_ERR_ARG
    assert lib.r6_pe_inventory_tls(
        source, len(blob), 1, ctypes.byref(lo), ctypes.byref(hi)) == R6_ERR_ARG
    assert lib.r6_pe_inventory_dll(
        source, len(blob), 0, name, 4, ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_BUFFER
    assert lib.r6_pe_inventory_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pe_inventory_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 84, 27)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pe_inventory_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, FUNC_OFF + 8, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pe_inventory_func(
        source, len(bad), 0, ctypes.byref(rva), ctypes.byref(end),
        ctypes.byref(length), ctypes.byref(leaf)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, DLL_OFF + 4, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_pe_inventory_dll(
        source, len(bad), 0, name, len(name), ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_FORMAT
    print("PE inventory: 70377 functions, 825 imports, 28 DLLs, 7 sections "
          "and PDB data match pe.json/pdata.json; bad blob, index, row and "
          "capacity rejected")


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
