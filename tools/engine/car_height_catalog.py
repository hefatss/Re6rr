r"""Pack shipped car height and aero offset row shapes.

    python tools/engine/car_height_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/car_height.r6chg

File paths, source sizes, row positions, aero slot labels and verbatim numeric
token bytes are copied. CP932 comments, ride-height roles and aero slot
semantics stay unparsed.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6CHG\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
FILE = struct.Struct("<4I")
ROW = struct.Struct("<5I")
PATTERN = "data/car/position/hightDown/CarHightDown_*.lua"
EXPECTED_FILES = 149
EXPECTED_BYTES = 1575214
EXPECTED_LINES = 231
HEIGHT_ROWS = 4
AERO_ROWS = 12
LABELS = "NABCDEFGHIJK"
NUMBER = rb"-?[0-9]+(?:\.[0-9]+)?"
HEIGHT_RE = re.compile(rb"^\s*(" + NUMBER + rb"),\s*--")
AERO_RE = re.compile(rb"^\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                     rb")\s*,\s*--\s*([NABCDEFGHIJK])\s*$")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/"))))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected car height corpus")
    files = []
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        if raw.count(b"\r\n") != EXPECTED_LINES:
            raise ValueError("unexpected car height line count: " + path)
        lines = raw.split(b"\r\n")[:-1]
        if lines[10].strip() != b"CarHightDownList = {" or \
                lines[42].strip() != b"CarAeroTireOffsetList = {" or \
                lines[15].strip() != b"}" or lines[55].strip() != b"}":
            raise ValueError("unexpected car height lists: " + path)
        base = len(rows)
        for local in range(HEIGHT_ROWS):
            match = HEIGHT_RE.match(lines[11 + local])
            if not match:
                raise ValueError("unexpected height row: " + path)
            rows.append((12 + local, match.group(1).strip(), None, ""))
        for local in range(AERO_ROWS):
            match = AERO_RE.match(lines[43 + local])
            if not match or match.group(3).decode("ascii") != LABELS[local]:
                raise ValueError("unexpected aero row: " + path)
            rows.append((44 + local, match.group(1).strip(),
                         match.group(2).strip(), LABELS[local]))
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
    for line, first, second, label in rows:
        first_span = add(first)
        second_span = add(second) if second else 0
        label_span = add(label.encode("ascii")) if label else 0
        row_records.extend(ROW.pack(line, first_span, second_span,
                                    label_span, len(label)))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows),
                         HEIGHT_ROWS * len(files) + AERO_ROWS * 2 * len(files),
                         EXPECTED_LINES, HEIGHT_ROWS, AERO_ROWS,
                         EXPECTED_BYTES, len(strings), 0)
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
                       "rows": [[r[0], r[1].decode("ascii"),
                                 r[2].decode("ascii") if r[2] else "",
                                 r[3]] for r in rows]}, stream, indent=2)
    print("%s: 149 files, 2384 rows, 4172 tokens, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
