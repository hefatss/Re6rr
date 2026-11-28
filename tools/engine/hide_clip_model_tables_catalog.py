r"""Pack shipped WANGAN hide-clip model-name table facts.

    python tools/engine/hide_clip_model_tables_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/hide_clip_model_tables.r6hcl

Dump-relative paths, file sizes, timestamps, table names and verbatim ASCII
model names are copied. No clip timing, render state or geometry is inferred.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6HCL\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
FILE = struct.Struct("<9I")
SPAN = struct.Struct("<2I")
PATTERN = os.path.join("data", "course", "stage", "A_TOKYO_NGT_EXT",
                       "WANGAN", "clip", "HIDECLIP_*.lua")
EXPECTED_FILES = 6
EXPECTED_BYTES = 140107
EXPECTED_NAMES = 2972
EXPECTED_LINES = 2994
EXPECTED_TABLES = 3
TIMESTAMP = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$")
NAME = re.compile(r'^\t"([A-Za-z0-9_]+)",$')


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split(os.sep))))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected hide-clip corpus")
    rows = []
    tables = []
    for path in paths:
        raw = open(path, "rb").read()
        lines = raw.decode("ascii").splitlines()
        offset = 1 if lines[0].startswith("-- CouraseClipEffect list") else 0
        timestamp = lines[offset]
        if not timestamp.startswith("-- ") or \
                not TIMESTAMP.match(timestamp[3:]):
            raise ValueError("bad hide-clip timestamp: " + path)
        table = lines[offset + 1]
        if not table.startswith("HIDE_MODEL_") or not table.endswith("\t= {"):
            raise ValueError("bad hide-clip table: " + path)
        table = table.split("\t= {", 1)[0]
        suffix = os.path.basename(path).rsplit("_", 1)[1][:-4]
        if table != "HIDE_MODEL_" + suffix:
            raise ValueError("hide-clip table/filename mismatch: " + path)
        names = []
        for line in lines[offset + 2:-1]:
            match = NAME.match(line)
            if not match:
                raise ValueError("bad hide-clip name: " + path)
            names.append(match.group(1))
        if lines[-1] != "}" or len(lines) != len(names) + offset + 3:
            raise ValueError("bad hide-clip frame: " + path)
        if table not in tables:
            tables.append(table)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), len(lines), timestamp[3:], table, names))
    if sum(row[2] for row in rows) != EXPECTED_LINES or \
            sum(len(row[5]) for row in rows) != EXPECTED_NAMES or \
            sorted(tables) != ["HIDE_MODEL_%02d" % index
                               for index in range(EXPECTED_TABLES)]:
        raise ValueError("unexpected hide-clip totals")
    return rows


def build(rows):
    name_count = sum(len(row[5]) for row in rows)
    strings_base = HEADER.size + len(rows) * FILE.size + name_count * SPAN.size
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

    name_spans = bytearray()
    file_rows = bytearray()
    for path, size, lines, timestamp, table, names in rows:
        spans = [add(value) for value in (path, table, timestamp)]
        fields = []
        for offset, length in spans:
            fields.extend((offset, length))
        fields.extend((size, lines, len(names)))
        file_rows.extend(FILE.pack(*fields))
        for name in names:
            offset, length = add(name)
            name_spans.extend(SPAN.pack(offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(rows), name_count,
                         len(strings), EXPECTED_BYTES, EXPECTED_LINES,
                         EXPECTED_TABLES)
    return header + bytes(file_rows) + bytes(name_spans) + bytes(strings)


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
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump([{"path": row[0], "bytes": row[1], "lines": row[2],
                        "timestamp": row[3], "table": row[4],
                        "names": row[5]} for row in rows], stream, indent=2)
    print("%s: %d hide-clip tables, %d names, %d bytes" %
          (args.out, len(rows), sum(len(row[5]) for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
