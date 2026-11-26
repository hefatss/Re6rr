"""Pack unported shipped native pointer-name tables into an R6NAM blob.

    python tools/engine/native_names_catalog.py --dump D:\\Games\\W6W-05 \
        --out build\\tmp\\native_names.r6nam

Rows come from wmn6r.exe pointer reads documented in docs/recon/NAME_TABLE.md.
No game data is committed; the output is derived data for the freestanding core.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
sys.path.insert(0, HERE)

import scene_config  # noqa: E402
from pe_report import PE  # noqa: E402

# (RVA, count) from docs/recon/NAME_TABLE.md; pointer_names() takes a VA.
IMAGE_BASE = 0x140000000
TABLES = {
    "sequence": (0x1D25A40, 469),
    "tk_ari": (0x1C61BE0, 156),
    "stage_time": (0x1E3B2B0, 126),
    "tips_end": (0x12FFD20, 100),
    "flash": (0x1CB3600, 86),
    "parts": (0x1E20C30, 42),
    "honor": (0x1E447B0, 31),
    "check_honor": (0x1E458F0, 13),
    "vinyl_blend": (0x1C56A80, 13),
}

MAGIC = b"R6NAM\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sI9I9I2I")


def collect(dump):
    pe = PE(os.path.join(dump, "wmn6r.exe"))
    return {name: scene_config.pointer_names(pe, IMAGE_BASE + rva, count)
            for name, (rva, count) in TABLES.items()}


def build(tables):
    names = list(TABLES)
    total = sum(len(tables[name]) for name in names)
    strings_off = HEADER.size + total * 4
    strings = bytearray()
    offsets = []
    for name in names:
        row = []
        for value in tables[name]:
            encoded = value.encode("utf8") + b"\0"
            row.append(strings_off + len(strings))
            strings.extend(encoded)
        offsets.append(row)
    header = HEADER.pack(MAGIC, VERSION,
                         *(len(tables[name]) for name in names),
                         *(strings_off for _ in names),
                         strings_off, len(strings))
    return header + b"".join(struct.pack("<%dI" % len(row), *row)
                             for row in offsets) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    tables = collect(args.dump)
    blob = build(tables)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d tables, %d names, %d bytes" %
          (args.out, len(tables), sum(map(len, tables.values())), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
