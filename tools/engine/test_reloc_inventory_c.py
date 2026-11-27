"""ctypes checks for the packed PE relocation inventory."""

import argparse
import bisect
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import reloc_inventory_catalog as ric  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
U32 = ctypes.c_uint32


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("directory_rva", U32),
                ("directory_size", U32), ("section_count", U32),
                ("block_count", U32), ("entry_count", U32),
                ("type_counts", U32 * 16)]


class Section(ctypes.Structure):
    _fields_ = [("rva", U32), ("size", U32)]


class Block(ctypes.Structure):
    _fields_ = [("page_rva", U32), ("block_size", U32),
                ("entry_first", U32), ("entry_count", U32),
                ("section_index", U32)]


class Entry(ctypes.Structure):
    _fields_ = [("offset", U32), ("type", U32), ("rva", U32),
                ("block_index", U32)]


def configure(lib):
    lib.r6_reloc_inventory_parse.restype = ctypes.c_int
    lib.r6_reloc_inventory_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                             ctypes.POINTER(Header)]
    lib.r6_reloc_inventory_section.restype = ctypes.c_int
    lib.r6_reloc_inventory_section.argtypes = [ctypes.c_char_p,
                                               ctypes.c_size_t, U32,
                                               ctypes.POINTER(Section)]
    lib.r6_reloc_inventory_block.restype = ctypes.c_int
    lib.r6_reloc_inventory_block.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                             U32, ctypes.POINTER(Block)]
    lib.r6_reloc_inventory_entry.restype = ctypes.c_int
    lib.r6_reloc_inventory_entry.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                             U32, ctypes.POINTER(Entry)]


def check(lib, sections, blocks, entries, types, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_reloc_inventory_parse(
        source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.directory_rva, header.directory_size,
            header.section_count, header.block_count, header.entry_count) == (
        1, ric.EXPECTED_RVA, ric.EXPECTED_SIZE, len(sections), len(blocks),
        len(entries))
    assert [header.type_counts[k] for k in range(16)] == \
        [types.get(k, 0) for k in range(16)]

    section = Section()
    for index, want in enumerate(sections):
        assert lib.r6_reloc_inventory_section(
            source, len(blob), index, ctypes.byref(section)) == R6_OK
        assert (section.rva, section.size) == want

    block = Block()
    for index, want in enumerate(blocks):
        assert lib.r6_reloc_inventory_block(
            source, len(blob), index, ctypes.byref(block)) == R6_OK
        assert (block.page_rva, block.block_size, block.entry_first,
                block.entry_count, block.section_index) == want

    entry = Entry()
    firsts = [row[2] for row in blocks]
    for index, (offset, kind) in enumerate(entries):
        owner = bisect.bisect_right(firsts, index) - 1
        assert lib.r6_reloc_inventory_entry(
            source, len(blob), index, ctypes.byref(entry)) == R6_OK
        assert (entry.offset, entry.type, entry.rva, entry.block_index) == (
            offset, kind, blocks[owner][0] + offset, owner)
    print("Relocation inventory: 7 sections, 1833 blocks and 270128 entries "
          "match the PE directory")

    assert lib.r6_reloc_inventory_section(
        source, len(blob), len(sections), ctypes.byref(section)) == R6_ERR_ARG
    assert lib.r6_reloc_inventory_block(
        source, len(blob), len(blocks), ctypes.byref(block)) == R6_ERR_ARG
    assert lib.r6_reloc_inventory_entry(
        source, len(blob), len(entries), ctypes.byref(entry)) == R6_ERR_ARG
    assert lib.r6_reloc_inventory_section(
        source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_reloc_inventory_block(
        source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_reloc_inventory_entry(
        source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_reloc_inventory_parse(
        source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_reloc_inventory_parse(
        source, len(blob) - 1, ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_reloc_inventory_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 0), (16, 554919), (20, 6), (24, 1832),
                        (28, 270127), (32, 824), (64, 269304)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_reloc_inventory_parse(
            source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT

    block_base = 96 + len(sections) * 8
    for slot, value in ((0, 0x107C001), (4, 6), (8, 1), (12, 1), (16, 7)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, block_base + slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_reloc_inventory_block(
            source, len(bad), 0, ctypes.byref(block)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, 96 + 4, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_reloc_inventory_parse(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT

    entry_base = block_base + len(blocks) * 20
    bad = bytearray(blob)
    struct.pack_into("<I", bad, entry_base, 0x1000)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_reloc_inventory_entry(
        source, len(bad), 0, ctypes.byref(entry)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, entry_base + 4, 16)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_reloc_inventory_entry(
        source, len(bad), 0, ctypes.byref(entry)) == R6_ERR_FORMAT
    print("Relocation negatives: bad magic/header/sections/blocks/entries, "
          "truncation and null outputs rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=os.path.join(
        r"D:\Games\W6W-05", "wmn6r.exe"))
    parser.add_argument("--pe", default=ric.PE_REPORT)
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"),
        r"D:\Games\W6W-05")
    configure(lib)
    _, sections, blocks, entries, types = ric.collect(args.exe, args.pe)
    check(lib, sections, blocks, entries, types,
          ric.build(sections, blocks, entries, types))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
