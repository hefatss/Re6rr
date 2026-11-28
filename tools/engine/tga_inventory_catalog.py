r"""Pack structural facts from AMUpdater TGA graphics.

    python tools/engine/tga_inventory_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/tga_inventory.r6tga

Header fields, sizes and footer presence are copied. Pixel bytes are not
copied and no image semantics are inferred.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6TGA\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
FILE = struct.Struct("<10I")
FOOTER = b"\0" * 8 + b"TRUEVISION-XFILE.\0"
EXPECTED_FILES = 8
RAW_TYPE = 2
RLE_TYPE = 10
PIXEL_BPP = (24, 32)


def collect(dump):
    root = os.path.join(dump, "AMCUS", "AMUpdaterData", "Graphics")
    paths = sorted(glob.glob(os.path.join(root, "*.tga")))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d TGA files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        if len(raw) < 18 + len(FOOTER):
            raise ValueError("short TGA: %s" % path)
        idlen, cmap, kind, first, length, cmap_bpp, x, y, width, height, \
            bpp, desc = struct.unpack_from("<3BHHBHHHHBB", raw, 0)
        if idlen or cmap or first or length or cmap_bpp or x or y or \
                not width or not height or bpp not in PIXEL_BPP or \
                kind not in (RAW_TYPE, RLE_TYPE) or \
                raw[-len(FOOTER):] != FOOTER:
            raise ValueError("unexpected TGA header/footer: %s" % path)
        if desc & 0xf0 or (bpp == 32 and desc & 0x0f not in (0, 8)) or \
                (bpp == 24 and desc & 0x0f):
            raise ValueError("unexpected TGA descriptor: %s" % path)
        pixels = width * height * bpp // 8
        exact = len(raw) == 18 + pixels + len(FOOTER)
        if kind == RAW_TYPE and not exact:
            raise ValueError("bad raw TGA size: %s" % path)
        if kind == RLE_TYPE and len(raw) >= 18 + pixels + len(FOOTER):
            raise ValueError("bad RLE TGA size: %s" % path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), kind, width, height, bpp, desc, pixels,
                     1 if exact else 0))
    return rows


def build(rows):
    strings_base = HEADER.size + len(rows) * FILE.size
    strings = bytearray()
    offsets = {}

    def add(value):
        raw = value.encode("ascii")
        found = offsets.get(raw)
        if found is not None:
            return found, len(raw)
        offset = strings_base + len(strings)
        offsets[raw] = offset
        strings.extend(raw + b"\0")
        return offset, len(raw)

    file_rows = bytearray()
    for row in rows:
        path_offset, path_length = add(row[0])
        file_rows.extend(FILE.pack(path_offset, path_length, *row[1:]))
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(strings),
        sum(row[1] for row in rows),
        sum(row[2] == RAW_TYPE for row in rows),
        sum(row[2] == RLE_TYPE for row in rows), len(rows))
    return header + bytes(file_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    rows = collect(args.dump)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump([{"path": row[0], "bytes": row[1], "type": row[2],
                        "size": (row[3], row[4]), "bpp": row[5],
                        "descriptor": row[6], "raw_exact": row[8]}
                       for row in rows], stream, indent=2)
    print("%s: %d TGA headers, %d bytes" % (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
