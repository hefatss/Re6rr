r"""Pack shipped car vinyl blend parameter table shapes.

    python tools/engine/color_vinyl_blend_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/color_vinyl_blend.r6cvb

Path, line counts, list/function names, row positions and verbatim numeric
token bytes are copied. CP932 comments, day/night/menu roles and reflection or
specular meanings stay unparsed.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6CVB\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<4I")
ROW = struct.Struct("<5I")
FUNC = struct.Struct("<3I")
RELATIVE = "data/car/color/ColorCommonParamerter.lua"
EXPECTED_BYTES = 8579
EXPECTED_LINES = 165
LISTS = ("MiniStickerLuminosityList", "CarVinylBlendParameterDayList",
         "CarVinylBlendParameterNightList", "CarVinylBlendParameterMenuList")
FUNCTIONS = ("getMiniStickerLuminosity", "GetCarVinylBlendParameterDay",
             "GetCarVinylBlendParameterNight", "GetCarVinylBlendParameterMenu")
NUMBER = rb"[0-9]+(?:\.[0-9]+)?"
SCALAR = re.compile(rb"^\s*(" + NUMBER + rb"),\s*--")
PAIR = re.compile(rb"^\s*\{\s*(" + NUMBER + rb"),\s*(" + NUMBER +
                  rb")\s*\},\s*--\s*(\d+)")
DECL = re.compile(rb"^function ([A-Za-z_]\w*)\(id\)$")


def collect(dump):
    path = os.path.join(dump, *RELATIVE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\r\n") != EXPECTED_LINES:
        raise ValueError("unexpected vinyl blend source")
    lines = raw.split(b"\r\n")[:-1]
    rows = []
    for list_index, name in enumerate(LISTS):
        start = next(i for i, line in enumerate(lines)
                     if line == name.encode("ascii") + b" = {")
        count = 2 if list_index == 0 else 20
        for offset in range(count):
            line = lines[start + 1 + offset]
            match = SCALAR.match(line) if list_index == 0 else PAIR.match(line)
            if not match:
                raise ValueError("unexpected vinyl blend row: " + name)
            tokens = match.groups()[:2]
            if list_index and int(match.group(3)) != 59 + offset:
                raise ValueError("unexpected vinyl blend index: " + name)
            rows.append((name, start + 2 + offset,
                         tuple(token.strip() for token in tokens)))
        if lines[start + 1 + count] != b"}":
            raise ValueError("unterminated vinyl blend list: " + name)
    functions = []
    for name in FUNCTIONS:
        found = [i for i, line in enumerate(lines)
                 if DECL.match(line) and DECL.match(line).group(1) ==
                 name.encode("ascii")]
        if len(found) != 1:
            raise ValueError("unexpected vinyl blend function: " + name)
        functions.append((name, found[0] + 1))
    if [row[1] for row in functions] != sorted(row[1] for row in functions):
        raise ValueError("unexpected vinyl blend function order")
    return rows, functions


def build(rows, functions):
    base = HEADER.size + FILE.size + len(rows) * ROW.size + \
        len(functions) * FUNC.size
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

    path_span = (add(RELATIVE.encode("ascii")), len(RELATIVE))
    file_row = FILE.pack(path_span[0], path_span[1],
                         EXPECTED_BYTES, EXPECTED_LINES)
    row_records = bytearray()
    for name, line, tokens in rows:
        raw = name.encode("ascii")
        span = add(raw)
        token_offsets = [add_token(token) for token in tokens]
        row_records.extend(ROW.pack(span, len(raw), line, token_offsets[0],
                                    len(tokens)))
    func_records = bytearray()
    for name, line in functions:
        raw = name.encode("ascii")
        span = add(raw)
        func_records.extend(FUNC.pack(span, len(raw), line))
    header = HEADER.pack(MAGIC, VERSION, 1, len(rows),
                         sum(len(row[2]) for row in rows), EXPECTED_LINES,
                         len(strings), EXPECTED_BYTES, len(functions), 0)
    return header + file_row + bytes(row_records) + bytes(func_records) + \
        bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    rows, functions = collect(args.dump)
    blob = build(rows, functions)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"rows": [[r[0], r[1], [t.decode("ascii") for t in r[2]]]
                                for r in rows],
                       "functions": functions}, stream, indent=2)
    print("%s: 62 rows, 122 tokens, 4 functions, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
