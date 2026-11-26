"""Pack the shipped Lua global call-site inventory into an R6LUA blob.

    python tools/engine/lua_globals_catalog.py \
        --out build/tmp/lua_globals.r6lua

Names, call counts and category order come from docs/recon/LUA_API.md, which was
derived from `wmn6r.exe` global lookups. No game data is committed; the blob is
derived data for the freestanding core.
"""

import argparse
import os
import re
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "LUA_API.md")

MAGIC = b"R6LUA\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
ROW = struct.Struct("<III")
NAME_RE = re.compile(r"^  (\S+)\s+(\d+)$", re.M)
CATEGORY_RE = re.compile(r"^## (.+?) \((\d+)\)$", re.M)


def collect(path=REPORT):
    with open(path, "r", encoding="utf-8") as stream:
        text = stream.read()
    categories = [match.group(1) for match in CATEGORY_RE.finditer(text)]
    rows = [(match.group(1), int(match.group(2)),
             CATEGORY_RE.findall(text[:match.start()]))
            for match in NAME_RE.finditer(text)]
    result = []
    for name, calls, before in rows:
        result.append({"name": name, "calls": calls,
                       "category": len(before) - 1})
    assert len(categories) == 7, len(categories)
    assert len(result) == 219, len(result)
    return categories, result


def build(categories, rows):
    strings = bytearray()
    offsets = []
    strings_off = HEADER.size + ROW.size * len(rows)
    for row in rows:
        offsets.append(strings_off + len(strings))
        strings.extend(row["name"].encode("utf8") + b"\0")
    payload = b"".join(ROW.pack(offsets[index], row["calls"],
                                row["category"])
                       for index, row in enumerate(rows))
    return (HEADER.pack(MAGIC, VERSION, len(rows), strings_off, len(strings)) +
            payload + bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    categories, rows = collect(args.report)
    blob = build(categories, rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d Lua globals, %d categories, %d bytes" %
          (args.out, len(rows), len(categories), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
