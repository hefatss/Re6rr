r"""Pack shipped story-rival block inventory facts.

    python tools/engine/rival_block_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/rival_block.r6rvb

Source path, ECharacter_* block names, line spans, five keyword row texts and
their per-block occurrence counts are copied. CP932 comments, float fields and
rival behavior are not decoded.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6RVB\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
BLOCK = struct.Struct("<19I")
RELATIVE = "data/Enma/ytConfigStoryRival.txt"
EXPECTED_BYTES = 145966
EXPECTED_LINES = 5261
EXPECTED_BLOCKS = 398
EXPECTED_UNIQUE = 201
KEYWORDS = ("Band", "Feature", "StartConfig", "EventFirst", "EventLast")
BLOCK_NAME = re.compile(r"^ECharacter_[A-Za-z0-9_]+$")
KEYWORD_ROW = re.compile(r"^\s{4}(Band|Feature|StartConfig|EventFirst|EventLast)\b(.*)$")


def collect(dump):
    path = os.path.join(dump, *RELATIVE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\n") != EXPECTED_LINES:
        raise ValueError("unexpected story rival source")
    text = raw.decode("cp932", errors="replace")
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines)
              if BLOCK_NAME.match(line.strip())]
    if len(starts) != EXPECTED_BLOCKS or \
            len({lines[index].strip() for index in starts}) != EXPECTED_UNIQUE:
        raise ValueError("unexpected story rival blocks")
    blocks = []
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(lines)
        rows = []
        counts = []
        for keyword in KEYWORDS:
            matches = [KEYWORD_ROW.match(line) for line in lines[start:end]]
            matches = [match for match in matches
                       if match and match.group(1) == keyword]
            if not matches:
                raise ValueError("missing story rival keyword: " + keyword)
            value = matches[0].group(0).strip()
            value = value.split("//", 1)[0].strip()
            value = re.sub(r"\s+", " ", value).strip()
            if any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in value):
                raise ValueError("non-ASCII story rival keyword row")
            rows.append((keyword + " " + value.split(" ", 1)[1]
                         if value != keyword else keyword))
            counts.append(len(matches))
        blocks.append((lines[start].strip(), start, end - start,
                       tuple(rows), tuple(counts)))
    return RELATIVE, len(raw), len(lines), blocks


def build(entry):
    path, size, lines, blocks = entry
    strings_base = HEADER.size + (len(blocks) + 1) * BLOCK.size
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

    path_span = add(path)
    block_rows = bytearray()
    for name, start, count, rows, counts in blocks:
        name_span = add(name)
        fields = [name_span[0], name_span[1], start, count]
        spans = [add(row) for row in rows]
        fields.extend(span[0] for span in spans)
        fields.extend(span[1] for span in spans)
        fields.extend(counts)
        block_rows.extend(BLOCK.pack(*fields))
    header = HEADER.pack(MAGIC, VERSION, 1, len(blocks), EXPECTED_UNIQUE,
                         len(strings), size, lines)
    return header + BLOCK.pack(path_span[0], path_span[1], 0, 0,
                               *([0] * 15)) + bytes(block_rows) + \
        bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    entry = collect(args.dump)
    blob = build(entry)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"path": entry[0], "bytes": entry[1],
                       "lines": entry[2], "blocks": entry[3]}, stream,
                      indent=2)
    print("%s: 398 rival blocks, 1,990 keyword rows, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
