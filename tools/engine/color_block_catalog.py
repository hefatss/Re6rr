r"""Pack shipped MA61 default/custom color block shapes.

    python tools/engine/color_block_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/color_block.r6clr

Paths, file line counts, block names, source line numbers and verbatim numeric
token bytes are copied. CP932 comments, color roles, icon/library enums and
float semantics stay unparsed.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6CLR\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s11I")
FILE = struct.Struct("<6I")
ROW = struct.Struct("<4I")
PATHS = ("data_jp/car/color/playerCar/PLC_MA61_DefaultColor.lua",
         "data_jp/car/color/playerCar/PLC_MA61_CustomColor.lua")
EXPECTED_BYTES = (8065, 32131)
EXPECTED_LINES = (247, 947)
EXPECTED_ROWS = (5, 40)
VEC4 = 3
FLOATS = 4
INTS = 3
BLOCK_LINES = 19
TOKEN = re.compile(rb"[0-9]+(?:\.[0-9]+)?")
VEC4_ROW = re.compile(rb"^\s*\{\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*\}")
SCALAR_ROW = re.compile(rb"^\s*([^,]+),\s*--")


def collect_file(dump, relative, size, count, rows):
    path = os.path.join(dump, *relative.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != size:
        raise ValueError("unexpected color source size: " + relative)
    lines = [line[:-1] if line.endswith(b"\r") else line
             for line in raw.split(b"\n")]
    if lines and not lines[-1]:
        lines.pop()
    if len(lines) != count:
        raise ValueError("unexpected color line count: " + relative)
    start = next(i for i, line in enumerate(lines)
                 if line.strip() == b"ColorList = {")
    blocks = []
    names = []
    for index in range(rows):
        base = start + 1 + index * BLOCK_LINES
        block = lines[base:base + BLOCK_LINES]
        if len(block) != BLOCK_LINES:
            raise ValueError("short color block: " + relative)
        name_match = re.match(rb'^\s*name\s*=\s*"(type[0-9]+)",', block[1])
        if not name_match or block[0].strip() != b"{" or \
                block[2].strip() != b"ListVec4 = {" or \
                block[6].strip() != b"}," or \
                block[7].strip() != b"ListFloat = {" or \
                block[12].strip() != b"}," or \
                block[13].strip() != b"ListInt = {" or \
                block[17].strip() != b"},":
            raise ValueError("unexpected color block header: " + relative)
        name = name_match.group(1).decode("ascii")
        if name != "type%d" % index:
            raise ValueError("color block name mismatch: " + relative)
        if b"-- end " + name.encode("ascii") not in block[18]:
            raise ValueError("color block end mismatch: " + relative)
        tokens = []
        for line in block[3:6]:
            match = VEC4_ROW.match(line)
            if not match:
                raise ValueError("unexpected vec4 row: " + relative)
            tokens.extend(match.group(n) for n in (1, 2, 3, 4))
        for line in block[8:12] + block[14:17]:
            match = SCALAR_ROW.match(line)
            if not match:
                raise ValueError("unexpected scalar row: " + relative)
            tokens.append(match.group(1))
        tokens = tuple(token.strip() for token in tokens)
        if len(tokens) != 19 or any(not TOKEN.fullmatch(token)
                                    for token in tokens):
            raise ValueError("unexpected color token: " + relative)
        names.append(name)
        blocks.append((name, base + 1, tuple(tokens)))
    return (relative, len(raw), len(lines), start + 2, blocks), names


def collect(dump):
    files = []
    for relative, size, count, rows in zip(PATHS, EXPECTED_BYTES,
                                           EXPECTED_LINES, EXPECTED_ROWS):
        entry, _ = collect_file(dump, relative, size, count, rows)
        files.append(entry)
    return files


def build(files):
    strings_base = HEADER.size + len(files) * FILE.size + \
        sum(len(entry[4]) for entry in files) * ROW.size
    strings = bytearray()
    offsets = {}

    def add(value):
        raw = value.encode("ascii")
        found = offsets.get(value)
        if found is not None:
            return found, len(raw)
        offset = strings_base + len(strings)
        offsets[value] = offset
        strings.extend(raw + b"\0")
        return offset, len(raw)

    file_rows = bytearray()
    row_records = bytearray()
    row_base = 0
    for path, size, lines, first, blocks in files:
        span = add(path)
        file_rows.extend(FILE.pack(span[0], span[1], size, lines,
                                   first, row_base))
        for name, line, tokens in blocks:
            name_span = add(name)
            token_base = strings_base + len(strings)
            for token in tokens:
                strings.extend(token + b"\0")
            row_records.extend(ROW.pack(name_span[0], name_span[1], line,
                                        token_base))
        row_base += len(blocks)
    header = HEADER.pack(MAGIC, VERSION, len(files),
                         sum(len(entry[4]) for entry in files),
                         sum(entry[2] for entry in files), len(strings),
                         sum(entry[1] for entry in files), 19, VEC4, FLOATS,
                         INTS, 0)
    return header + bytes(file_rows) + bytes(row_records) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files = collect(args.dump)
    blob = build(files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": [{"path": entry[0], "size": entry[1],
                                  "lines": entry[2], "first": entry[3],
                                  "rows": [[r[0], r[1],
                                            [t.decode("ascii") for t in r[2]]]
                                           for r in entry[4]]}
                               for entry in files]}, stream, indent=2)
    print("%s: 45 color blocks, 855 tokens, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
