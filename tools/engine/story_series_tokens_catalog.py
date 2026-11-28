r"""Pack shipped story-series configuration token lines.

    python tools/engine/story_series_tokens_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/story_series_tokens.r6sst

The source file, block headers and token lines before `//` comments are copied
verbatim. No race, story or carryover rule is inferred.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6SST\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
BLOCK = struct.Struct("<3I")
SPAN = struct.Struct("<2I")
SOURCE = "data/Enma/ytConfigStorySeries.txt"
SOURCE_SIZE = 28433
SOURCE_LINES = 1511
EXPECTED_BLOCKS = 125
HEADER_LINE = re.compile(r"^ESeries_[A-Za-z0-9_]+")


def collect(dump):
    path = os.path.join(dump, *SOURCE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != SOURCE_SIZE:
        raise ValueError("unexpected ytConfigStorySeries.txt size")
    text = raw.decode("cp932", errors="replace")
    lines = text.splitlines()
    if len(lines) != SOURCE_LINES:
        raise ValueError("unexpected ytConfigStorySeries.txt line count")
    blocks = []
    for line in lines:
        tokens = line.split("//", 1)[0]
        if HEADER_LINE.match(tokens):
            blocks.append([tokens, []])
        elif blocks and tokens.strip():
            blocks[-1][1].append(tokens)
    if len(blocks) != EXPECTED_BLOCKS or \
            any(not block[1] for block in blocks):
        raise ValueError("unexpected story-series block shape")
    for header, group in blocks:
        for value in [header] + group:
            if len(value) > 96 or any(ord(ch) < 9 or ord(ch) > 126 or
                                      (ord(ch) < 32 and ch != "\t")
                                      for ch in value):
                raise ValueError("non-ASCII story-series token line")
    return blocks


def build(blocks):
    line_total = sum(len(group) for _, group in blocks)
    strings_base = HEADER.size + len(blocks) * BLOCK.size + \
        line_total * SPAN.size
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

    block_rows = bytearray()
    spans = bytearray()
    for header, group in blocks:
        header_offset, header_length = add(header)
        block_rows.extend(BLOCK.pack(header_offset, header_length,
                                     len(group)))
        for value in group:
            offset, length = add(value)
            spans.extend(SPAN.pack(offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(blocks), line_total,
                         len(strings), SOURCE_SIZE, SOURCE_LINES)
    return header + bytes(block_rows) + bytes(spans) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    blocks = collect(args.dump)
    blob = build(blocks)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump([{"header": header, "lines": group}
                       for header, group in blocks], stream, indent=2)
    print("%s: %d story-series blocks, %d token lines, %d bytes" %
          (args.out, len(blocks), sum(len(group) for _, group in blocks),
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
