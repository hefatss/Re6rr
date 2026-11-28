r"""Pack shipped introductory-motion file/wait facts.

    python tools/engine/introductory_motions_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/introductory_motions.r6int

File names, wait frames, two scalar frames and accessor names are copied. No
motion payload or animation semantics are inferred.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6INT\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
ROW = struct.Struct("<5I")
SOURCE = "data/motion/introduction/IntroductoryMotions.lua"
SOURCE_SIZE = 2443
WAITS = (20, 60)


def collect(dump):
    path = os.path.join(dump, *SOURCE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != SOURCE_SIZE:
        raise ValueError("unexpected IntroductoryMotions.lua size: %d" %
                         len(raw))
    text = raw.decode("utf-8-sig")
    start = int(re.search(r"START_FRAME\s*=\s*(\d+)", text).group(1))
    blank = int(re.search(r"BLANK_FRAME\s*=\s*(\d+)", text).group(1))
    rows = []
    for name in ("DEFAULT", "ZENICHI"):
        match = re.search(name + r"\s*=\s*\{\s*\"([^\"]+)\"\s*,"
                          r"\s*\"([^\"]+)\"\s*,\s*(\d+)\s*\}", text)
        if not match:
            raise ValueError("missing motion row: " + name)
        rows.append((match.group(1), match.group(2), int(match.group(3))))
    functions = re.findall(r"function\s+([A-Za-z_]\w*)", text)
    names = [name for row in rows for name in row[:2]]
    if (start, blank) != (0, 0) or len(rows) != 2 or \
            tuple(row[2] for row in rows) != WAITS or \
            len(functions) != 6 or len(set(names)) != 4 or \
            any(not name.endswith(".MED") for name in names):
        raise ValueError("unexpected introductory-motion table facts")
    return start, blank, rows, functions


def build(collection):
    start, blank, rows, functions = collection
    strings_base = HEADER.size + len(rows) * ROW.size + len(functions) * 8
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

    row_bytes = bytearray()
    for left, right, wait in rows:
        left_span = add(left)
        right_span = add(right)
        row_bytes.extend(ROW.pack(left_span[0], left_span[1], right_span[0],
                                  right_span[1], wait))
    function_bytes = bytearray()
    for name in functions:
        offset, length = add(name)
        function_bytes.extend(struct.pack("<2I", offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(rows), 4, len(functions),
                         len(strings), start, blank)
    return header + bytes(row_bytes) + bytes(function_bytes) + bytes(strings)


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
        start, blank, rows, functions = collection
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"start_frame": start, "blank_frame": blank,
                       "rows": rows, "functions": functions}, stream,
                      indent=2)
    print("%s: 2 motion rows, 4 names and %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
