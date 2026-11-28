r"""Pack shipped charCar default color block shapes.

    python tools/engine/char_color_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/char_color.r6ccc

Paths, source sizes, line counts, COLOR_MAX, block names, row positions and
verbatim numeric token bytes are copied. CP932 comments, color roles and enum
meanings stay unparsed.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6CCC\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s11I")
FILE = struct.Struct("<8I")
ROW = struct.Struct("<4I")
PATTERN = "data/car/color/charCar/CRC_*_DefaultColor.lua"
EXPECTED_FILES = 100
EXPECTED_BYTES = 535375
EXPECTED_MAXES = (95, 4, 1)
BLOCK_LINES = 18
TOKENS_PER_ROW = 19
NUMBER = rb"-?[0-9]+(?:\.[0-9]+)?"
VEC4_ROW = re.compile(rb"^\s*\{\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                      rb")\s*,\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                      rb")\s*,\s*\}")
SCALAR_ROW = re.compile(rb"^\s*(" + NUMBER + rb"),\s*--")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/"))))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected charCar color corpus")
    files = []
    rows = []
    maxes = {1: 0, 3: 0, 6: 0}
    for path in paths:
        raw = open(path, "rb").read()
        sep = b"\r\n" if b"\r\n" in raw else b"\n"
        lines = raw.split(sep)
        if lines and not lines[-1]:
            lines.pop()
        header = [line for line in lines
                  if line.strip().startswith(b"COLOR_MAX")]
        if len(header) != 1:
            raise ValueError("unexpected COLOR_MAX: " + path)
        color_max = int(header[0].split(b"=")[1].split(b"--")[0].strip())
        if color_max not in maxes:
            raise ValueError("unexpected COLOR_MAX value: " + path)
        maxes[color_max] += 1
        starts = [i for i, line in enumerate(lines)
                  if line.strip() == b"ColorList = {"]
        if len(starts) != 1:
            raise ValueError("unexpected ColorList: " + path)
        start = starts[0]
        named = bool(re.match(rb'^\s*name\s*=\s*"type0",', lines[start + 2]))
        block_lines = 19 if named else 18
        base = len(rows)
        for local in range(color_max):
            at = start + 1 + local * block_lines
            block = lines[at:at + block_lines]
            if len(block) != block_lines or block[0].strip() != b"{":
                raise ValueError("short color block: " + path)
            offset = 1 if named else 0
            name_match = re.match(rb'^\s*name\s*=\s*"(type[0-9]+)",',
                                  block[1]) if named else None
            if named and (not name_match or name_match.group(1).decode(
                    "ascii") != "type%d" % local):
                raise ValueError("unexpected color block name: " + path)
            if block[1 + offset].strip() != b"ListVec4 = {" or \
                    b"-- end" not in block[-1] or \
                    block[5 + offset].strip() != b"}," or \
                    block[6 + offset].strip() != b"ListFloat = {" or \
                    block[11 + offset].strip() != b"}," or \
                    block[12 + offset].strip() != b"ListInt = {" or \
                    block[16 + offset].strip() != b"},":
                raise ValueError("unexpected color block shape: " + path)
            tokens = []
            for line in block[2 + offset:5 + offset]:
                match = VEC4_ROW.match(line)
                if not match:
                    raise ValueError("unexpected vec4 row: " + path)
                tokens.extend(match.group(n) for n in (1, 2, 3, 4))
            for line in block[7 + offset:11 + offset] + \
                    block[13 + offset:16 + offset]:
                match = SCALAR_ROW.match(line)
                if not match:
                    raise ValueError("unexpected scalar row: " + path)
                tokens.append(match.group(1))
            tokens = tuple(token.strip() for token in tokens)
            if len(tokens) != TOKENS_PER_ROW:
                raise ValueError("unexpected color token count: " + path)
            rows.append(("type%d" % local, at + 1, tokens))
        files.append((os.path.basename(path), len(raw), len(lines),
                      color_max, start + 1, base, block_lines))
    if tuple(maxes[value] for value in (1, 6, 3)) != EXPECTED_MAXES:
        raise ValueError("unexpected COLOR_MAX distribution")
    return files, rows


def build(files, rows):
    base = HEADER.size + len(files) * FILE.size + len(rows) * ROW.size
    strings = bytearray()
    offsets = {}

    def add(value):
        found = offsets.get(value)
        if found is not None:
            return found
        offset = base + len(strings)
        offsets[value] = offset
        strings.extend(value + b"\0")
        return offset

    def add_token(value):
        offset = base + len(strings)
        strings.extend(value + b"\0")
        return offset

    file_rows = bytearray()
    for name, size, lines, color_max, start, row_base, block_lines in files:
        raw = name.encode("ascii")
        span = add(raw)
        file_rows.extend(FILE.pack(span, len(raw), size, lines, color_max,
                                   start, row_base, block_lines))
    row_records = bytearray()
    for name, line, tokens in rows:
        raw = name.encode("ascii")
        span = add(raw)
        token_offset = add_token(tokens[0])
        for token in tokens[1:]:
            add_token(token)
        row_records.extend(ROW.pack(span, len(raw), line, token_offset))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows),
                         len(rows) * TOKENS_PER_ROW,
                         sum(entry[2] for entry in files),
                         sum(entry[1] for entry in files), len(strings),
                         *EXPECTED_MAXES, 0)
    return header + bytes(file_rows) + bytes(row_records) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, rows = collect(args.dump)
    blob = build(files, rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": files,
                       "rows": [[r[0], r[1], [t.decode("ascii")
                                             for t in r[2]]]
                                for r in rows]}, stream, indent=2)
    print("%s: 100 files, 122 blocks, 2318 tokens, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
