r"""Pack path/layout facts from stage-effect PCV tables.

    python tools/engine/pcv_inventory_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/stage_effect.r6pcv

Dump-relative paths, byte spans and float-triple counts are packed. Float
bit patterns are not copied and no stage/effect semantics are inferred.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6PCV\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<5I")
STRIDE = 12
EXPECTED_FILES = 757
EXPECTED_BYTES = 234612
EXPECTED_TRIPLES = 19551


def collect(dump):
    paths = sorted(glob.glob(os.path.join(
        dump, "data", "effect", "stage_effect", "**", "PCV_*.bin"),
        recursive=True))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d PCV files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in paths:
        size = os.path.getsize(path)
        if not size or size % STRIDE:
            raise ValueError("bad PCV length: %s" % path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     size, size // STRIDE))
    if sum(row[1] for row in rows) != EXPECTED_BYTES or \
            sum(row[2] for row in rows) != EXPECTED_TRIPLES:
        raise ValueError("unexpected PCV corpus totals")
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
    for path, size, triples in rows:
        path_offset, path_length = add(path)
        file_rows.extend(FILE.pack(path_offset, path_length, size, triples,
                                   STRIDE))
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(strings),
        sum(row[1] for row in rows), sum(row[2] for row in rows))
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
            json.dump([{"path": row[0], "bytes": row[1], "triples": row[2]}
                       for row in rows], stream, indent=2)
    print("%s: %d PCV files, %d triples, %d bytes" %
          (args.out, len(rows), sum(row[2] for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
