r"""Pack row counts and small integer facts from ghost-region Lua tables.

    python tools/engine/ghost_region_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/ghost_region.r6grl

Paths, counts and literal integers are copied. No region semantics or game
behaviour is inferred.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6GRL\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
FILE = struct.Struct("<11I")
EXPECTED_FILES = 7
DEFEATED_RE = re.compile(rb"^\s*(\d+),\s*(\d+),\s*(\d+),\s*$")
REGION_RE = re.compile(rb"^\s*\{\s*(\d+),\s*\},")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(
        dump, "data", "ghost", "lua", "b071_18_*.lua")))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d ghost-region Lua files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        lines = raw.splitlines()
        defeated = []
        regions = []
        functions = 0
        for line in lines:
            match = DEFEATED_RE.match(line)
            if match:
                values = tuple(int(part) for part in match.groups())
                defeated.append(values)
                continue
            match = REGION_RE.match(line)
            if match:
                regions.append(int(match.group(1)))
                continue
            if line.strip().startswith(b"function"):
                functions += 1
        if len(defeated) != 1 or len(regions) != 47 or functions != 2:
            raise ValueError("unexpected ghost-region rows: %s" % path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), len(lines), defeated[0], len(regions),
                     min(regions), max(regions), functions))
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
    for path, size, lines, defeated, regions, first, last, functions in rows:
        path_offset, path_length = add(path)
        file_rows.extend(FILE.pack(path_offset, path_length, size, lines,
                                   regions, first, last, functions,
                                   *defeated))
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(strings),
        sum(row[1] for row in rows), sum(row[2] for row in rows),
        sum(row[4] for row in rows), sum(row[7] for row in rows))
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
            json.dump([{"path": row[0], "bytes": row[1], "lines": row[2],
                        "defeated": row[3], "regions": row[4],
                        "functions": row[7]} for row in rows],
                      stream, indent=2)
    print("%s: %d ghost-region files, %d regions, %d bytes" %
          (args.out, len(rows), sum(row[4] for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
