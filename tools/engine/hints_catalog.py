r"""Pack the fixed-stride record layout of the shipped hints file.

    python tools/engine/hints_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/hints.r6hnt

The single path, byte total, stride, row count and copied 16-byte records are
packed. No hint text, name or meaning is inferred.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6HNT\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
ROW = struct.Struct("<4I")
SOURCE = "hints.dat"
SOURCE_SIZE = 1072
STRIDE = 16
EXPECTED_ROWS = 67
EXPECTED_DISTINCT = 61


def collect(dump):
    path = os.path.join(dump, SOURCE)
    raw = open(path, "rb").read()
    if len(raw) != SOURCE_SIZE or len(raw) % STRIDE:
        raise ValueError("unexpected hints.dat size: %d" % len(raw))
    rows = [struct.unpack_from("<4I", raw, at)
            for at in range(0, len(raw), STRIDE)]
    if len(rows) != EXPECTED_ROWS or len(set(rows)) != EXPECTED_DISTINCT or \
            any(row[3] >> 24 for row in rows):
        raise ValueError("unexpected hints.dat record layout")
    return rows


def build(rows):
    header = HEADER.pack(MAGIC, VERSION, len(rows), STRIDE, SOURCE_SIZE,
                         len(set(rows)))
    return header + b"".join(ROW.pack(*row) for row in rows)


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
            json.dump([list(row) for row in rows], stream, indent=2)
    print("%s: %d hints records, %d bytes" % (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
