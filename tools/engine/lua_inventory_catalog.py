"""Pack shipped Lua script inventory counts into an R6LSI blob.

    python tools/engine/lua_inventory_catalog.py \
        --out build/tmp/lua_inventory.r6lsi

Counts and directory names come from docs/recon/lua.json. Noisy undefined and
native-candidate name lists are intentionally not packed; only counts are
ported. No dump data is committed.
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
HEADER = struct.Struct("<8s17I")
DIR = struct.Struct("<IIIII")


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
    return roots, dirs


def build(roots, dirs):
    strings_off = HEADER.size + DIR.size * len(dirs)
    strings = bytearray()
    offsets = []
    for row in dirs:
        offsets.append(strings_off + len(strings))
        strings.extend(row["dir"].encode("ascii") + b"\0")

    payload = b"".join(
        DIR.pack(row["root"], offsets[index], row["files"], row["bytes"],
                 row["with_logic"])
        for index, row in enumerate(dirs))
    fields = [VERSION, len(roots)]
    for root in roots:
        fields.extend(root[key] for key in (
            "files", "bytes", "defined", "calls", "undefined",
            "native_candidates"))
    fields.extend((len(dirs), strings_off, len(strings)))
    return HEADER.pack(MAGIC, *fields) + payload + bytes(strings)


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
