"""Pack the recovered unlock/honor-condition schema into an R6HON blob.

    python tools/engine/honor_schema_catalog.py \
        --out build/tmp/honor_schema.r6hon

Type names come from the shipped `check_honor_*` pointer table; field order comes
from factory 0x1409109c0 label providers documented in STORY_NATIVE.md. No
per-episode predicate instances exist in the dump, so this is schema only.
"""

import argparse
import os
import re
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "STORY_NATIVE.md")

MAGIC = b"R6HON\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
ROW = struct.Struct("<IIIIIII")
FIELD_MAX = 5
ROW_RE = re.compile(r"^\| (\d+) \| `([^`]+)` \| ([^|]+) \|$", re.M)


def collect(path=REPORT):
    with open(path, "r", encoding="utf-8") as stream:
        text = stream.read()
    result = []
    for match in ROW_RE.finditer(text):
        fields = [field.strip() for field in match.group(3).split(",")
                  if field.strip() and field.strip() != "none"]
        result.append({"type": int(match.group(1)),
                       "name": match.group(2), "fields": fields})
    assert len(result) == 13, len(result)
    assert [row["type"] for row in result] == list(range(13))
    assert all(len(row["fields"]) <= FIELD_MAX for row in result)
    return result


def build(rows):
    strings = bytearray()
    strings_off = HEADER.size + ROW.size * len(rows)

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("utf8") + b"\0")
        return offset

    payload = b""
    for row in rows:
        name_off = add(row["name"])
        field_offsets = [add(field) for field in row["fields"]]
        while len(field_offsets) < FIELD_MAX:
            field_offsets.append(0)
        payload += ROW.pack(name_off, len(row["fields"]), *field_offsets)
    return (HEADER.pack(MAGIC, VERSION, len(rows), strings_off, len(strings)) +
            payload + bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = collect(args.report)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d honor types, %d fields, %d bytes" %
          (args.out, len(rows), sum(len(row["fields"]) for row in rows),
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
