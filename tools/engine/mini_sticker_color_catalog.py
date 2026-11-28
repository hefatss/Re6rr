r"""Pack shipped mini-sticker color row shapes.

    python tools/engine/mini_sticker_color_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/mini_sticker_color.r6msc

File paths, source sizes, row positions, bank indices and verbatim numeric
token bytes are copied. CP932 color names and bank semantics stay unparsed.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6MSC\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<4I")
ROW = struct.Struct("<5I")
PATTERN = "data/car/color/mini_sticker/getMiniStickerColor_*.lua"
EXPECTED_FILES = 417
EXPECTED_BYTES = 986467
EXPECTED_LINES = 61
VINYL_MAX = 10
ROWS_PER_FILE = 20
NUMBER = rb"[0-9]+(?:\.[0-9]+)?"
ROW_RE = re.compile(rb"^\s*\{\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                    rb")\s*,\s*(" + NUMBER + rb")\s*,\s*\},\s*--\s+\S+\s+(\d+)")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/"))))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected mini-sticker corpus")
    files = []
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        if raw.count(b"\r\n") != EXPECTED_LINES:
            raise ValueError("unexpected mini-sticker line count: " + path)
        lines = raw.split(b"\r\n")[:-1]
        starts = [i for i, line in enumerate(lines)
                  if line.strip() == b"MiniStickerColorList = {"]
        if starts != [15] or b"VINYL_COLOR_MAX =  10" not in lines:
            raise ValueError("unexpected mini-sticker header: " + path)
        base = len(rows)
        for local in range(ROWS_PER_FILE):
            source_line = 16 + local + (local >= 10)
            match = ROW_RE.match(lines[source_line])
            if not match or int(match.group(4)) != local % 10:
                raise ValueError("unexpected mini-sticker row: " + path)
            rows.append((source_line + 1, local % 10,
                         tuple(token.strip() for token in match.groups()[:3])))
        if lines[37].strip() != b"}":
            raise ValueError("unterminated mini-sticker list: " + path)
        files.append((os.path.basename(path), len(raw), base))
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

    file_rows = bytearray()
    for name, size, row_base in files:
        raw = name.encode("ascii")
        span = add(raw)
        file_rows.extend(FILE.pack(span, len(raw), size, row_base))
    row_records = bytearray()
    for line, slot, tokens in rows:
        spans = [add(token) for token in tokens]
        row_records.extend(ROW.pack(line, slot, spans[0], spans[1],
                                    spans[2]))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows),
                         len(rows) * 3, EXPECTED_LINES, VINYL_MAX,
                         EXPECTED_BYTES, len(strings), 0)
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
    print("%s: 417 files, 8340 rows, 25020 tokens, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
