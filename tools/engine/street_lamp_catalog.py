r"""Pack fixed-stride record layout facts from street-lamp tables.

    python tools/engine/street_lamp_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/street_lamp.r6slp

Paths, byte spans, record counts and copied u32 flag ranges are packed.
Coordinate floats are not copied and no lighting semantics are inferred.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6SLP\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<8I")
STRIDE = 28
EXPECTED_FILES = 168
EXPECTED_RECORDS = 24916
EXPECTED_BYTES = 697648


def collect(dump):
    paths = sorted(glob.glob(os.path.join(
        dump, "data", "course", "street_lamp", "**", "LAMP_*.bin"),
        recursive=True))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d street-lamp files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        if not raw or len(raw) % STRIDE:
            raise ValueError("bad street-lamp length: %s" % path)
        count = len(raw) // STRIDE
        flags = struct.unpack_from("<%dI" % count, raw, 24)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), count, min(flags), max(flags), len(set(flags))))
    if sum(row[1] for row in rows) != EXPECTED_BYTES or \
            sum(row[2] for row in rows) != EXPECTED_RECORDS:
        raise ValueError("unexpected street-lamp corpus totals")
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
    for path, size, count, minimum, maximum, distinct in rows:
        path_offset, path_length = add(path)
        file_rows.extend(FILE.pack(path_offset, path_length, size, count,
                                   STRIDE, minimum, maximum, distinct))
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(strings),
        sum(row[1] for row in rows), sum(row[2] for row in rows), STRIDE)
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
            json.dump([{"path": row[0], "bytes": row[1], "records": row[2],
                        "flag_range": (row[3], row[4]), "distinct": row[5]}
                       for row in rows], stream, indent=2)
    print("%s: %d street-lamp files, %d records, %d bytes" %
          (args.out, len(rows), sum(row[2] for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
