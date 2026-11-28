r"""Pack shipped stage-effect filename list facts.

    python tools/engine/stage_effect_filename_lists_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/stage_effect_filename_lists.r6sfl

Source paths, byte sizes and copied ASCII `.lua` basenames are packed. No
effect behavior or numeric fields are inferred.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6SFL\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s4I")
FILE = struct.Struct("<4I")
SPAN = struct.Struct("<2I")
PATTERN = "data/effect/stage_effect/**/parameter/filename.txt"
EXPECTED_FILES = 6
EXPECTED_BYTES = 1023
EXPECTED_NAMES = 34


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/")),
                             recursive=True))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected stage-effect filename-list corpus")
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        lines = raw.decode("ascii").splitlines()
        if not lines or lines[0] != "filename.txt" or len(lines) < 2:
            raise ValueError("bad filename list header: " + path)
        names = lines[1:]
        if any(not name or not name.isprintable() or
               not name.endswith(".lua") for name in names):
            raise ValueError("bad filename list row: " + path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), names))
    if sum(len(row[2]) for row in rows) != EXPECTED_NAMES:
        raise ValueError("unexpected stage-effect filename-list total")
    return rows


def build(rows):
    strings_base = HEADER.size + len(rows) * FILE.size + \
        sum(len(row[2]) for row in rows) * SPAN.size
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
    name_rows = bytearray()
    for path, size, names in rows:
        offset, length = add(path)
        file_rows.extend(FILE.pack(offset, length, size, len(names)))
        for name in names:
            offset, length = add(name)
            name_rows.extend(SPAN.pack(offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(rows),
                         sum(len(row[2]) for row in rows), len(strings))
    return header + bytes(file_rows) + bytes(name_rows) + bytes(strings)


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
            json.dump([{"path": path, "bytes": size, "names": names}
                       for path, size, names in rows], stream, indent=2)
    print("%s: %d filename lists, %d names, %d bytes" %
          (args.out, len(rows), sum(len(row[2]) for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
