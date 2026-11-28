r"""Pack shipped NeonColor.lua row spans without decoding float values.

    python tools/engine/neon_color_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/neon_color.r6neo

Path, source line numbers, six row positions, verbatim numeric token bytes and
comment presence are copied. CP932 comment text, [1]/[2]/[3] return order and
out-of-range fallback behavior stay unparsed.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6NEO\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
ROW = struct.Struct("<8I")
RELATIVE = os.path.join("data", "car", "color", "NeonColor.lua")
EXPECTED_BYTES = 1180
EXPECTED_LINES = 31
EXPECTED_ROWS = 6
FIRST_LINE = 9
ROW_PATTERN = re.compile(
    rb"^    \{\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)\s*\},\s*--")


def collect(dump):
    path = os.path.join(dump, RELATIVE)
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\r\n") != EXPECTED_LINES:
        raise ValueError("unexpected NeonColor source")
    lines = raw.split(b"\r\n")
    if len(lines) != EXPECTED_LINES + 1 or lines[-1]:
        raise ValueError("unexpected NeonColor line layout")
    rows = []
    for index in range(EXPECTED_ROWS):
        line = lines[FIRST_LINE + index - 1]
        match = ROW_PATTERN.match(line)
        if not match:
            raise ValueError("unexpected NeonColor row %d" % index)
        rows.append(tuple(match.group(n) for n in (1, 2, 3)))
    return RELATIVE.replace("\\", "/"), len(raw), len(lines) - 1, rows


def build(entry):
    path, size, lines, rows = entry
    strings_base = HEADER.size + len(rows) * ROW.size
    strings = bytearray()
    offsets = {}

    def add(value):
        found = offsets.get(value)
        if found is not None:
            return found, len(value)
        offset = strings_base + len(strings)
        offsets[value] = offset
        strings.extend(value + b"\0")
        return offset, len(value)

    path_span = add(path.encode("ascii"))
    row_records = bytearray()
    for index, tokens in enumerate(rows):
        spans = [add(token) for token in tokens]
        row_records.extend(ROW.pack(spans[0][0], spans[1][0], spans[2][0],
                                    spans[0][1], spans[1][1], spans[2][1],
                                    1, FIRST_LINE + index))
    header = HEADER.pack(MAGIC, VERSION, 1, len(rows), lines,
                         len(strings), size, len(rows), 0,
                         path_span[0], path_span[1])
    return header + bytes(row_records) + bytes(strings)


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
                       "lines": entry[2],
                       "rows": [[t.decode("ascii") for t in row]
                                for row in entry[3]]}, stream, indent=2)
    print("%s: 6 NeonColor rows, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
