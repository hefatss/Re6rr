r"""Pack shipped DISTCLIP integer table facts.

    python tools/engine/distclip_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/distclip.r6dcl

Source paths, global table names, key names and active integer rows are copied.
Comment lines and clip rendering behavior are not stored or interpreted.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6DCL\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<8I")
ROW = struct.Struct("<3I")
PATTERN = "data/course/stage/**/clip/DISTCLIP_*.lua"
EXPECTED_FILES = 395
EXPECTED_BYTES = 83284
EXPECTED_ROWS = 3950
KEYS = ("ROAD", "ONRD", "LONG", "NEAR", "LODM", "CAST", "BACK", "REFC",
        "REFR", "RFBG")
TABLE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*\{\s*$")
PAIR = re.compile(r"^\s*([A-Z]+)\s*=\s*(-?\d+),?\s*$")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/")),
                             recursive=True))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected DISTCLIP corpus")
    files = []
    row_total = 0
    for path in paths:
        raw = open(path, "rb").read()
        text = raw.decode("ascii", errors="replace")
        lines = text.splitlines()
        tables = [m.group(1) for line in lines if (m := TABLE.match(line))]
        rows = [(m.group(1), int(m.group(2)))
                for line in lines if (m := PAIR.match(line))]
        if len(tables) != 1 or len(rows) != 10 or \
                any(key not in KEYS for key, _ in rows) or \
                len(set(key for key, _ in rows)) != 10:
            raise ValueError("bad DISTCLIP shape: " + path)
        if not (tables[0] == "DEFAULT_CLIP_DISTANCE" or
                re.fullmatch(r"CLIP_DISTANCE_\d\d", tables[0])):
            raise ValueError("unknown DISTCLIP table: " + path)
        if any(value < 0 or value > 50000 for _, value in rows):
            raise ValueError("out-of-range DISTCLIP value: " + path)
        relative = os.path.relpath(path, dump).replace("\\", "/")
        files.append((relative, len(raw), len(lines), tables[0], rows))
        row_total += len(rows)
    if row_total != EXPECTED_ROWS:
        raise ValueError("unexpected DISTCLIP row total")
    return files


def build(files):
    rows = [row for entry in files for row in entry[4]]
    strings_base = HEADER.size + len(files) * FILE.size + len(rows) * ROW.size
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
    row_rows = bytearray()
    row_base = 0
    for path, size, lines, table, pairs in files:
        path_span = add(path)
        table_span = add(table)
        file_rows.extend(FILE.pack(path_span[0], path_span[1],
                                   table_span[0], table_span[1], size, lines,
                                   row_base, len(pairs)))
        for key, value in pairs:
            key_span = add(key)
            row_rows.extend(ROW.pack(key_span[0], key_span[1], value))
        row_base += len(pairs)
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows),
                         len(strings), EXPECTED_BYTES)
    return header + bytes(file_rows) + bytes(row_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files = collect(args.dump)
    blob = build(files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump([{"path": entry[0], "bytes": entry[1], "lines": entry[2],
                        "table": entry[3], "rows": entry[4]} for entry in files],
                      stream, indent=2)
    print("%s: %d DISTCLIP files, %d integer rows, %d bytes" %
          (args.out, len(files), len(files) * 10, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
