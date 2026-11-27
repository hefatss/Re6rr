r"""Pack the shipped wmn6r.exe base relocation table into an R6RLC blob.

    python tools/engine/reloc_inventory_catalog.py \
        --exe D:\Games\W6W-05\wmn6r.exe \
        --out build/tmp/reloc_inventory.r6rlc

The PE data directory 5 is walked strictly by block size, not by stopping at a
zero page. Page RVA, block size, entry offset/type and the section owning each
page are copied. No relocation is applied and no executable bytes are copied.
"""

import argparse
import collections
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))

from pe_report import PE, u16, u32  # noqa: E402

MAGIC = b"R6RLC\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I16I")
SECTION = struct.Struct("<2I")
BLOCK = struct.Struct("<5I")
ENTRY = struct.Struct("<2I")
PAGE_SIZE = 0x1000
DIRECTORY_INDEX = 5
EXPECTED_RVA = 0x201C000
EXPECTED_SIZE = 554920
EXPECTED_SECTIONS = 7
EXPECTED_BLOCKS = 1833
EXPECTED_ENTRIES = 270128
EXPECTED_TYPES = {0: 825, 10: 269303}
PE_REPORT = os.path.join(ROOT, "docs", "recon", "pe.json")


def collect(exe, pe_report=PE_REPORT):
    image = PE(exe)
    directory_rva, directory_size = image.dirs[DIRECTORY_INDEX]
    if (directory_rva, directory_size) != (EXPECTED_RVA, EXPECTED_SIZE):
        raise ValueError("unexpected relocation directory %r/%d" %
                         (directory_rva, directory_size))
    sections = [(section["vaddr"], section["vsize"])
                for section in image.sections]
    if len(sections) != EXPECTED_SECTIONS:
        raise ValueError("expected %d sections, found %d" %
                         (EXPECTED_SECTIONS, len(sections)))
    for rva, size in sections:
        if not size or rva + size > image.size_of_image:
            raise ValueError("bad section range %x/%x" % (rva, size))

    offset = image.off(directory_rva)
    if offset is None:
        raise ValueError("relocation directory outside raw data")
    end = offset + directory_size
    at = offset
    blocks = []
    entries = []
    types = collections.Counter()
    while at < end:
        if at + 8 > end:
            raise ValueError("truncated relocation block header")
        page = u32(image.raw, at)
        block_size = u32(image.raw, at + 4)
        if block_size < 8 or block_size % 2 or at + block_size > end:
            raise ValueError("bad relocation block size %d" % block_size)
        owners = [index for index, (rva, size) in enumerate(sections)
                  if rva <= page < rva + size and
                  page + PAGE_SIZE <= rva + size]
        if len(owners) != 1:
            raise ValueError("relocation page %x outside one section" % page)
        first = len(entries)
        count = (block_size - 8) // 2
        for local in range(count):
            word = u16(image.raw, at + 8 + 2 * local)
            kind = word >> 12
            delta = word & 0x0FFF
            if kind >= 16 or page + delta >= image.size_of_image:
                raise ValueError("bad relocation entry %x:%d" % (page, delta))
            entries.append((delta, kind))
            types[kind] += 1
        blocks.append((page, block_size, first, count, owners[0]))
        at += block_size
    if at != end or len(blocks) != EXPECTED_BLOCKS or \
            len(entries) != EXPECTED_ENTRIES or dict(types) != EXPECTED_TYPES:
        raise ValueError("unexpected relocation counts %d/%d/%s" %
                         (len(blocks), len(entries), dict(types)))

    with open(pe_report, "r", encoding="utf8") as stream:
        report = json.load(stream)
    if report["relocations"] != {"blocks": EXPECTED_BLOCKS,
                                 "entries": EXPECTED_ENTRIES}:
        raise ValueError("relocation counts disagree with pe.json")
    return image, sections, blocks, entries, types


def build(sections, blocks, entries, types):
    section_off = HEADER.size
    block_off = section_off + len(sections) * SECTION.size
    entry_off = block_off + len(blocks) * BLOCK.size
    counts = [types.get(kind, 0) for kind in range(16)]
    header = HEADER.pack(MAGIC, VERSION, EXPECTED_RVA, EXPECTED_SIZE,
                         len(sections), len(blocks), len(entries), *counts)
    section_payload = b"".join(SECTION.pack(*row) for row in sections)
    block_payload = b"".join(BLOCK.pack(*row) for row in blocks)
    entry_payload = b"".join(ENTRY.pack(*row) for row in entries)
    assert entry_off == HEADER.size + len(sections) * SECTION.size + \
        len(blocks) * BLOCK.size
    return header + section_payload + block_payload + entry_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=os.path.join(
        r"D:\Games\W6W-05", "wmn6r.exe"))
    parser.add_argument("--pe", default=PE_REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    _, sections, blocks, entries, types = collect(args.exe, args.pe)
    blob = build(sections, blocks, entries, types)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d sections, %d blocks, %d entries, %d bytes" %
          (args.out, len(sections), len(blocks), len(entries), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
