r"""Pack shipped course-debug TDB id/name facts.

    python tools/engine/debug_tdb_registry_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/debug_tdb_registry.r6dtr

Source paths, byte sizes, copied hexadecimal ids, decimal comments, ASCII
names, blink names and accessor names are packed. No rendering or gameplay
meaning is inferred.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6DTR\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<4I")
PAIR = struct.Struct("<4I")
SPAN = struct.Struct("<2I")
TABLE_GLOB = "data/course/debug/DEBUG_TDB_A_*.lua"
ACCESSOR = "data/course/debug/DebugAccessor.lua"
BLINK = "data/course/debug/DEBUG_BLINK_NUDS_LIST.lua"
EXPECTED_FILES = 23
EXPECTED_PAIRS = 12087
EXPECTED_ACCESSORS = 10
EXPECTED_BLINKS = 4
ID_MIN = 0x10000000
ID_MAX = 0x150000FD
ROW = re.compile(r'^"0x([0-9a-fA-F]+)",\s*"([^"]+)",\s*--\s*(\d+)\s*$')


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *TABLE_GLOB.split("/"))))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d TDB files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    files = []
    pairs = []
    for path in paths:
        raw = open(path, "rb").read()
        text = raw.decode("cp932", errors="replace")
        found = []
        for line in text.splitlines():
            match = ROW.match(line)
            if match:
                found.append((int(match.group(1), 16), match.group(2),
                              int(match.group(3))))
        if not found:
            raise ValueError("no TDB rows in " + path)
        for item, name, decimal in found:
            if item != decimal or not ID_MIN <= item <= ID_MAX or \
                    not name.isascii() or not name.isprintable():
                raise ValueError("bad TDB row in " + path)
        files.append((os.path.relpath(path, dump).replace("\\", "/"),
                      len(raw), found))
        pairs.extend(found)
    if len(pairs) != EXPECTED_PAIRS or \
            len(set(item for item, _, _ in pairs)) != 2674 or \
            len(set(name for _, name, _ in pairs)) != 4264:
        raise ValueError("unexpected TDB corpus totals")
    if len(set(path for path, _, _ in files)) != EXPECTED_FILES:
        raise ValueError("duplicate TDB path")
    accessor_raw = open(os.path.join(dump, *ACCESSOR.split("/")), "rb").read()
    blink_raw = open(os.path.join(dump, *BLINK.split("/")), "rb").read()
    accessors = re.findall(r"function\s+([A-Za-z_]\w*)",
                           accessor_raw.decode("cp932", errors="replace"))
    blink_text = blink_raw.decode("cp932", errors="replace")
    match = re.search(r"DEBUG_BLINK_NUDS\s*=\s*\{(.*?)\}", blink_text, re.S)
    blinks = re.findall(r'"([^"]+)"', match.group(1)) if match else []
    if len(accessors) != EXPECTED_ACCESSORS or \
            len(blinks) != EXPECTED_BLINKS or \
            len(set(accessors)) != len(accessors) or \
            len(set(blinks)) != len(blinks) or \
            any(not name.startswith("GetDebug") for name in accessors) or \
            any(not name.isascii() or not name.isprintable()
                for name in blinks):
        raise ValueError("unexpected debug accessor or blink facts")
    return (files, pairs, accessors, blinks, len(accessor_raw),
            len(blink_raw))


def build(collection):
    files, pairs, accessors, blinks, accessor_size, blink_size = collection
    strings_base = (HEADER.size + len(files) * FILE.size +
                    len(pairs) * PAIR.size +
                    (len(blinks) + len(accessors)) * SPAN.size)
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
    for path, size, group in files:
        offset, length = add(path)
        file_rows.extend(FILE.pack(offset, length, size, len(group)))
    pair_rows = bytearray()
    for item, name, decimal in pairs:
        offset, length = add(name)
        pair_rows.extend(PAIR.pack(item, decimal, offset, length))
    spans = bytearray()
    for name in blinks + accessors:
        offset, length = add(name)
        spans.extend(SPAN.pack(offset, length))
    header = HEADER.pack(
        MAGIC, VERSION, len(files), len(pairs), len(strings),
        sum(size for _, size, _ in files), len(accessors), accessor_size,
        len(blinks), blink_size)
    return (header + bytes(file_rows) + bytes(pair_rows) + bytes(spans) +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    collection = collect(args.dump)
    blob = build(collection)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        files, pairs, accessors, blinks, _, _ = collection
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({
                "files": [{"path": path, "bytes": size,
                           "pairs": len(group)}
                          for path, size, group in files],
                "pairs": pairs, "accessors": accessors, "blinks": blinks,
            }, stream, indent=2)
    print("%s: %d TDB files, %d pairs, %d bytes" %
          (args.out, len(collection[0]), len(collection[1]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
