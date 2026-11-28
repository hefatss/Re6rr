r"""Pack shipped related-section integer row facts.

    python tools/engine/related_section_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/related_section.r6rsh

Paths, file sizes, LOAD_SPEED integers and raw six-integer row pairs are
copied. Section ids and ordering carry no assigned meaning.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6RSH\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<6I")
PAIR = struct.Struct("<12I")
EXPECTED_FILES = 5
EXPECTED_PAIRS = 540
LOAD_SPEED = (5, 5)


def collect(dump):
    paths = sorted(glob.glob(os.path.join(
        dump, "data", "course", "parameter", "relation",
        "RelatedSection*.lua")))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d related-section files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        text = raw.decode("utf-8-sig", errors="replace")
        load = re.search(r"LOAD_SPEED\s*=\s*\{([^}]*)\}", text).group(1)
        load = tuple(int(value) for value in re.findall(r"\d+", load))
        found = re.findall(r"\{\s*\{([^{}]*)\}\s*,\s*\{([^{}]*)\}\s*,\s*\}",
                           text)
        pairs = []
        for left, right in found:
            values = [int(value) for value in
                      re.findall(r"\d+", left) + re.findall(r"\d+", right)]
            if len(values) != 12:
                raise ValueError("bad related-section row: " + path)
            pairs.append(tuple(values))
        if load != LOAD_SPEED or not pairs:
            raise ValueError("unexpected related-section header: " + path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), load, pairs))
    if sum(len(row[3]) for row in rows) != EXPECTED_PAIRS:
        raise ValueError("unexpected related-section corpus total")
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
    pairs = bytearray()
    for path, size, load, group in rows:
        path_offset, path_length = add(path)
        file_rows.extend(FILE.pack(path_offset, path_length, size, len(group),
                                   load[0], load[1]))
        for values in group:
            pairs.extend(PAIR.pack(*values))
    header = HEADER.pack(MAGIC, VERSION, len(rows), len(strings),
                         sum(len(row[3]) for row in rows),
                         LOAD_SPEED[0], LOAD_SPEED[1])
    return header + bytes(file_rows) + bytes(strings) + bytes(pairs)


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
            json.dump([{"path": row[0], "bytes": row[1],
                        "load_speed": row[2], "pairs": row[3]}
                       for row in rows], stream, indent=2)
    print("%s: %d related-section files, %d row pairs, %d bytes" %
          (args.out, len(rows), sum(len(row[3]) for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
