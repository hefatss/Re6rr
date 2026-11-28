r"""Pack shipped side-sticker and vinyl color row shapes.

    python tools/engine/sticker_color_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/sticker_color.r6stc

Paths, corpus kind, row lines, selector ids and verbatim numeric token bytes
are copied. CP932 color names and palette roles stay unparsed.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6STC\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<5I")
ROW = struct.Struct("<5I")
SOURCES = (("data/car/color/side_sticker/getSideStickerColor_*.lua", 0, 47),
           ("data/car/color/vinyl/getVinylColor_*.lua", 1, 111))
EXPECTED_BYTES = 350159
EXPECTED_LINES = 9749
ROWS_PER_FILE = 10
NUMBER = rb"[0-9]+(?:\.[0-9]+)?"
ROW_RE = re.compile(rb"^\s*\{\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                    rb")\s*,\s*(" + NUMBER + rb")\s*,\s*\},\s*--\s*\S+\s+([0-9]+)")


def collect(dump):
    paths = []
    for pattern, kind, count in SOURCES:
        found = sorted(glob.glob(os.path.join(dump, *pattern.split("/"))))
        if len(found) != count:
            raise ValueError("unexpected sticker color corpus: " + pattern)
        paths.extend((path, kind) for path in found)
    if sum(os.path.getsize(path) for path, _ in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected sticker color bytes")
    files = []
    rows = []
    lines_total = 0
    for path, kind in paths:
        raw = open(path, "rb").read()
        sep = b"\r\n" if b"\r\n" in raw else b"\n"
        lines = raw.split(sep)
        if lines and not lines[-1]:
            lines.pop()
        lines_total += len(lines)
        starts = [i for i, line in enumerate(lines)
                  if line.strip().endswith(b"ColorList = {")]
        if len(starts) != 1:
            raise ValueError("unexpected color list: " + path)
        start = starts[0]
        base = len(rows)
        for local in range(ROWS_PER_FILE):
            match = ROW_RE.match(lines[start + 1 + local])
            if not match or int(match.group(4)) != local:
                raise ValueError("unexpected color row: " + path)
            rows.append((start + 2 + local, local,
                         tuple(match.group(n).strip() for n in (1, 2, 3))))
        files.append((os.path.basename(path), kind, len(raw), base))
    if lines_total != EXPECTED_LINES or len(rows) != 1580:
        raise ValueError("unexpected sticker color totals: %d %d" %
                         (lines_total, len(rows)))
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
    for name, kind, size, row_base in files:
        raw = name.encode("ascii")
        span = add(raw)
        file_rows.extend(FILE.pack(span, len(raw), kind, size, row_base))
    row_records = bytearray()
    for line, ident, tokens in rows:
        spans = [add(token) for token in tokens]
        row_records.extend(ROW.pack(line, ident, spans[0], spans[1], spans[2]))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows), 47, 111,
                         EXPECTED_BYTES, EXPECTED_LINES, len(strings), 0)
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
                       "rows": [[a, b, [t.decode("ascii") for t in c]]
                                for a, b, c in rows]}, stream, indent=2)
    print("%s: 158 files, 1580 rows, 4740 tokens, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
