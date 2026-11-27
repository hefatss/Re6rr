r"""Pack header and array facts from every shipped .EES scene file.

    python tools/engine/ees_inventory_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/ees_inventory.r6ees

Facts come from tools/engine/ees_scene.py, which validates the camera/car
header arithmetic against each file size. Only the path, kind, counts, header
size and array name/count/stride/offset/size are copied; array contents are not
included or interpreted.
"""

import argparse
import json
import os
import struct

import ees_scene

MAGIC = b"R6EESI\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
FILE = struct.Struct("<11I")
ARRAY = struct.Struct("<6I")
EXPECTED_FILES = 1129
KINDS = ("cam", "car")


def collect(dump):
    raw = ees_scene.collect(dump)["files"]
    rows = []
    for path in sorted(raw):
        item = raw[path]
        rows.append((path, item["kind"], item["version"], item["file_size"],
                     item["count"], item.get("effect_count", 0),
                     item["header_size"],
                     [(array["name"], array["count"], array["stride"],
                       array["offset"], array["size"])
                      for array in item["arrays"]]))
    if len(rows) != EXPECTED_FILES:
        raise ValueError("expected %d .EES files, found %d" %
                         (EXPECTED_FILES, len(rows)))
    return rows


def build(rows):
    strings = bytearray()
    arrays = bytearray()
    files = bytearray()

    def add(value):
        offset = len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    first = 0
    for path, kind, version, size, count, effect_count, header_size, values in rows:
        path_off = add(path)
        for name, array_count, stride, offset, array_size in values:
            name_off = add(name)
            arrays.extend(ARRAY.pack(name_off, len(name), array_count,
                                     stride, offset, array_size))
        files.extend(FILE.pack(path_off, len(path), size, KINDS.index(kind),
                               version, count, effect_count, header_size,
                               first, len(values), 0))
        first += len(values)
    header = HEADER.pack(MAGIC, VERSION, len(rows), first, len(strings))
    return header + bytes(files) + bytes(arrays) + bytes(strings)


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
            json.dump([{"path": row[0], "kind": row[1], "version": row[2],
                        "size": row[3], "count": row[4],
                        "effect_count": row[5], "header": row[6],
                        "arrays": row[7]} for row in rows], stream, indent=2)
    print("%s: %d .EES files, %d arrays, %d bytes" %
          (args.out, len(rows), sum(len(row[7]) for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
