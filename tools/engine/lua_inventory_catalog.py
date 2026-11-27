"""Pack shipped Lua script inventory counts and names into an R6LSI blob.

    python tools/engine/lua_inventory_catalog.py \
        --out build/tmp/lua_inventory.r6lsi

Counts, directory names and the shipped defined/native/undefined name lists
come from docs/recon/lua.json. No dump data is committed.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "lua.json")

MAGIC = b"R6LSI\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s29I")
DIR = struct.Struct("<IIIII")
NAME = struct.Struct("<I")
TOP = struct.Struct("<II")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    roots = []
    dirs = []
    for root_index, item in enumerate(data["roots"]):
        roots.append({
            "files": item["files"], "bytes": item["bytes"],
            "defined": item["defined"], "calls": item["calls"],
            "undefined": item["undefined"],
            "native_candidates": item["native_candidates"],
            "defined_names": item["defined_names"],
            "native_top": item["native_top"],
            "undefined_top": item["undefined_top"],
        })
        for folder in item["dirs"]:
            dirs.append({
                "root": root_index,
                "dir": folder["dir"],
                "files": folder["files"],
                "bytes": folder["bytes"],
                "with_logic": folder["with_logic"],
            })
    assert len(roots) == 2
    assert len(dirs) == 158
    assert all(row["dir"] and row["dir"].isascii() and "/" not in row["dir"]
               for row in dirs)
    assert [len(row["defined_names"]) for row in roots] == [812, 440]
    assert [len(row["native_top"]) for row in roots] == [149, 66]
    assert [len(row["undefined_top"]) for row in roots] == [200, 80]
    assert all(len(pair) == 2 for row in roots
               for kind in ("native_top", "undefined_top")
               for pair in row[kind])
    return roots, dirs


def build(roots, dirs):
    rows_start = HEADER.size + DIR.size * len(dirs)
    symbol_rows = sum(
        len(root["defined_names"]) * NAME.size +
        len(root["native_top"]) * TOP.size +
        len(root["undefined_top"]) * TOP.size
        for root in roots)
    strings_off = rows_start + symbol_rows
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("utf8") + b"\0")
        return offset

    dir_offsets = [add(row["dir"]) for row in dirs]
    dir_payload = b"".join(
        DIR.pack(row["root"], dir_offsets[index], row["files"], row["bytes"],
                 row["with_logic"])
        for index, row in enumerate(dirs))

    symbol_payload = bytearray()
    descriptors = []
    for root in roots:
        defined_off = rows_start + len(symbol_payload)
        for name in root["defined_names"]:
            symbol_payload.extend(NAME.pack(add(name)))
        native_off = rows_start + len(symbol_payload)
        for name, count in root["native_top"]:
            symbol_payload.extend(TOP.pack(add(name), count))
        undefined_off = rows_start + len(symbol_payload)
        for name, count in root["undefined_top"]:
            symbol_payload.extend(TOP.pack(add(name), count))
        descriptors.extend((
            len(root["defined_names"]), defined_off,
            len(root["native_top"]), native_off,
            len(root["undefined_top"]), undefined_off))

    fields = [VERSION, len(roots)]
    for root in roots:
        fields.extend(root[key] for key in (
            "files", "bytes", "defined", "calls", "undefined",
            "native_candidates"))
    fields.extend((len(dirs), strings_off, len(strings)))
    fields.extend(descriptors)
    assert len(fields) == 29
    return (HEADER.pack(MAGIC, *fields) + dir_payload +
            bytes(symbol_payload) + bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    roots, dirs = collect(args.report)
    blob = build(roots, dirs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: 2 roots, %d dirs, %d bytes" % (args.out, len(dirs), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
