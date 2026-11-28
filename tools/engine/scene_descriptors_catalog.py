r"""Pack shipped Scene.Lua descriptor facts.

    python tools/engine/scene_descriptors_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/scene_descriptors.r6scd

Source paths, copied data-root and environment strings, I_EVENT_NUM and the
empty S_EVENT table shape are packed. No camera or scene semantics are inferred.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6SCD\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s3I")
FILE = struct.Struct("<9I")
ENVIRONMENT = "/Environment.Lua"
EXPECTED_FILES = 70
EXPECTED_BYTES = 8629
ROW = re.compile(
    r'^S_DATA_ROOT = "([^"]+)"\n'
    r'S_ENVIRONMENT_DATA = "([^"]+)"\n'
    r'I_EVENT_NUM =\s+(\d+)\n'
    r'S_EVENT = \{\n'
    r'\}\n?$')


def collect(dump):
    paths = sorted(glob.glob(os.path.join(
        dump, "data_jp", "scene", "**", "Scene.Lua"), recursive=True))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected Scene.Lua corpus")
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        match = ROW.match(raw.decode("ascii"))
        if not match or match.group(2) != ENVIRONMENT or \
                int(match.group(3)) != 0:
            raise ValueError("bad Scene.Lua shape: " + path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), match.group(1), match.group(2),
                     int(match.group(3)), 0))
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
    for path, size, root, environment, event_num, event_count in rows:
        spans = [add(value) for value in (path, root, environment)]
        fields = []
        for offset, length in spans:
            fields.extend((offset, length))
        fields.extend((size, event_num, event_count))
        file_rows.extend(FILE.pack(*fields))
    header = HEADER.pack(MAGIC, VERSION, len(rows), len(strings))
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
            json.dump([{"path": row[0], "bytes": row[1],
                        "root": row[2], "environment": row[3],
                        "event_num": row[4], "event_count": row[5]}
                       for row in rows], stream, indent=2)
    print("%s: %d Scene.Lua descriptors, %d bytes" %
          (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
