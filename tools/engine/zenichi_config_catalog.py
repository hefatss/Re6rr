r"""Pack shipped Zenichi name-plate table facts.

    python tools/engine/zenichi_config_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/zenichi_config.r6znc

Item IDs, variation/layout integers and texture names are copied. No title or
reward semantics are inferred.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6ZNC\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s4I")
ROW = struct.Struct("<5I")
SOURCE = "data_jp/menu/Zenichi/ZenichiConfig.lua"
SOURCE_SIZE = 30209
EXPECTED_ROWS = 276


def collect(dump):
    path = os.path.join(dump, *SOURCE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != SOURCE_SIZE:
        raise ValueError("unexpected ZenichiConfig.lua size: %d" % len(raw))
    text = raw.decode("utf-8-sig")
    match = re.search(r"NAME_PLATE_INFO\s*=\s*\{(.*?)\n\}", text, re.S)
    if not match:
        raise ValueError("NAME_PLATE_INFO table not found")
    found = re.findall(
        r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*\"([^\"]+)\"\s*,\s*(\d+)\s*\}",
        match.group(1))
    rows = [(int(item), int(variation), name, int(layout))
            for item, variation, name, layout in found]
    if len(rows) != EXPECTED_ROWS or \
            [row[0] for row in rows] != list(range(1, EXPECTED_ROWS + 1)):
        raise ValueError("unexpected Zenichi name-plate row ids")
    if min(row[1] for row in rows) != 1 or max(row[1] for row in rows) != 6 or \
            min(row[3] for row in rows) != 0 or max(row[3] for row in rows) != 1:
        raise ValueError("unexpected Zenichi variation/layout ranges")
    return rows


def build(rows):
    strings_base = HEADER.size + len(rows) * ROW.size
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

    row_bytes = bytearray()
    for item, variation, name, layout in rows:
        name_offset, name_length = add(name)
        row_bytes.extend(ROW.pack(item, variation, name_offset, name_length,
                                  layout))
    header = HEADER.pack(MAGIC, VERSION, len(rows), len(strings), SOURCE_SIZE)
    return header + bytes(row_bytes) + bytes(strings)


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
            json.dump([{"item": row[0], "variation": row[1],
                        "texture": row[2], "layout": row[3]}
                       for row in rows], stream, indent=2)
    print("%s: %d Zenichi name-plate rows, %d bytes" %
          (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
