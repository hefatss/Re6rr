r"""Pack shipped vinyl selector row shapes.

    python tools/engine/vinyl_select_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/vinyl_select.r6vsl

Paths, selector IDs, row lines and verbatim numeric value tokens are copied.
CP932 labels and selection roles stay unparsed.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6VSL\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<4I")
ROW = struct.Struct("<3I")
PATTERN = "data/car/color/vinyl_select/getVinylSelect_*.lua"
EXPECTED_FILES = 149
EXPECTED_BYTES = 722358
EXPECTED_LINES = 93
ROWS_PER_FILE = 50
ID_MIN = 59
ID_MAX = 108
ROW_RE = re.compile(rb"^\s*([0-9]+),\s*--\s*([0-9]+)\s")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/"))))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected vinyl selector corpus")
    files = []
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        sep = b"\r\n" if b"\r\n" in raw else b"\n"
        lines = raw.split(sep)
        if lines and not lines[-1]:
            lines.pop()
        if len(lines) != EXPECTED_LINES or \
                lines[14].strip() != b"VinylSelectList = {" or \
                lines[65].strip() != b"}":
            raise ValueError("unexpected vinyl selector layout: " + path)
        base = len(rows)
        for local in range(ROWS_PER_FILE):
            match = ROW_RE.match(lines[15 + local])
            if not match:
                raise ValueError("unexpected vinyl selector row: " + path)
            value = match.group(1).strip()
            ident = int(match.group(2))
            if ident != ID_MIN + local:
                raise ValueError("unexpected vinyl selector id: " + path)
            rows.append((16 + local, ident, value))
        files.append((os.path.basename(path), len(raw), base))
    return files, rows


def build(files, rows):
    base = HEADER.size + len(files) * FILE.size + len(rows) * ROW.size
    strings = bytearray()
    offsets = {}

    def add(value):
        found = offsets.get(value)
        if found is not None:
            return found
        offset = base + len(strings)
        offsets[value] = offset
        strings.extend(value + b"\0")
        return offset

    file_rows = bytearray()
    for name, size, row_base in files:
        raw = name.encode("ascii")
        span = add(raw)
        file_rows.extend(FILE.pack(span, len(raw), size, row_base))
    row_records = bytearray()
    for line, ident, value in rows:
        row_records.extend(ROW.pack(line, ident, add(value)))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows),
                         EXPECTED_BYTES, EXPECTED_LINES, ID_MIN, ID_MAX,
                         len(strings), 0)
    return header + bytes(file_rows) + bytes(row_records) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, rows = collect(args.dump)
    blob = build(files, rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": files,
                       "rows": [[a, b, c.decode("ascii")] for a, b, c in rows]},
                      stream, indent=2)
    print("%s: 149 files, 7450 rows, 50 ids, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
