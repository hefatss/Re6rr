r"""Pack shipped custom-frame id-to-texture-name facts.

    python tools/engine/custom_frame_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/custom_frame.r6cfm

Ids, copied texture names and accessor names are packed. No frame behaviour,
texture payload or UI semantics are inferred.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6CFM\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
ROW = struct.Struct("<9I")
SOURCE = "data_jp/menu/menuTex/Customframe/Customframe.lua"
SOURCE_SIZE = 26386
EXPECTED_ROWS = 183
EXPECTED_NAMES = 732


def collect(dump):
    path = os.path.join(dump, *SOURCE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != SOURCE_SIZE:
        raise ValueError("unexpected Customframe.lua size: %d" % len(raw))
    text = raw.decode("utf-8-sig")
    found = re.findall(
        r'\{\s*(\d+)\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,'
        r'\s*"([^"]+)"\s*\}', text)
    rows = [(int(item), tuple(names)) for item, *names in found]
    names = [name for _, group in rows for name in group]
    functions = re.findall(r"function\s+([A-Za-z_]\w*)", text)
    if len(rows) != EXPECTED_ROWS or \
            [row[0] for row in rows] != list(range(1, EXPECTED_ROWS + 1)) or \
            len(names) != EXPECTED_NAMES or len(set(names)) != len(names) or \
            len(functions) != 6:
        raise ValueError("unexpected custom-frame table shape")
    if any(len(name) != 21 or not name.startswith("cmn_cf_") or
           not name.endswith(".nut") for name in names):
        raise ValueError("unexpected custom-frame texture name")
    return rows, functions


def build(collection):
    rows, functions = collection
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
    for item, names in rows:
        spans = [add(name) for name in names]
        fields = [item] + [span[0] for span in spans] + \
            [span[1] for span in spans]
        row_bytes.extend(ROW.pack(*fields))
    function_bytes = bytearray()
    for name in functions:
        offset, length = add(name)
        function_bytes.extend(struct.pack("<2I", offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(rows), EXPECTED_NAMES,
                         len(functions), len(strings), SOURCE_SIZE)
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
        rows, functions = collection
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"rows": rows, "functions": functions}, stream,
                      indent=2)
    print("%s: %d custom frames, %d texture names, %d bytes" %
          (args.out, len(collection[0]), EXPECTED_NAMES, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
