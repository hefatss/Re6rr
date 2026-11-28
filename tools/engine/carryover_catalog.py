r"""Pack shipped ytCarryover.txt token facts.

    python tools/engine/carryover_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/carryover.r6cry

Series token, six scalar lines and four fixed data rows are copied verbatim.
Carryover rules, checkpoint tokens, coordinates and float semantics are not
decoded.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6CRY\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
PREAMBLE = struct.Struct("<4I")
ROW = struct.Struct("<15I")
RELATIVE = "data/Enma/ytCarryover.txt"
EXPECTED_BYTES = 398
EXPECTED_LINES = 10
NUMBER = r"[0-9.+-]+"
ROW_PATTERN = re.compile(
    r"^\s*(true|false),\s*\{\s*(\d+),\s*([A-Za-z0-9_]+),\s*(" + NUMBER +
    r"),\s*(" + NUMBER + r"),\s*(" + NUMBER +
    r")\s*\},\s*(" + NUMBER + r")\s*$")


def collect(dump):
    path = os.path.join(dump, *RELATIVE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\r\n") != EXPECTED_LINES:
        raise ValueError("unexpected carryover source")
    lines = raw.decode("ascii").splitlines()
    if len(lines) != EXPECTED_LINES:
        raise ValueError("unexpected carryover line count")
    preamble = []
    for index, line in enumerate(lines[:6]):
        token = line.strip()
        if not token:
            raise ValueError("empty carryover preamble")
        preamble.append((token, 0 if index == 0 else 1, index + 1))
    rows = []
    for index, line in enumerate(lines[6:]):
        match = ROW_PATTERN.match(line)
        if not match:
            raise ValueError("unexpected carryover row")
        rows.append(tuple(match.groups()) + (index + 7,))
    if len(rows) != 4:
        raise ValueError("unexpected carryover row count")
    return RELATIVE, len(raw), len(lines), preamble, rows


def build(entry):
    path, size, lines, preamble, rows = entry
    strings_base = HEADER.size + (len(preamble) + 1) * PREAMBLE.size + \
        len(rows) * ROW.size
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
    preamble_rows = bytearray()
    for value, kind, line in preamble:
        span = add(value)
        preamble_rows.extend(PREAMBLE.pack(span[0], span[1], kind, line))
    row_rows = bytearray()
    for bool_text, number, token, a, b, c, tail, line in rows:
        spans = [add(value) for value in (bool_text, number, token, a, b, c,
                                          tail)]
        fields = []
        for span in spans:
            fields.extend(span)
        fields.append(line)
        row_rows.extend(ROW.pack(*fields))
    header = HEADER.pack(MAGIC, VERSION, 1, len(preamble) + 1, len(rows),
                         len(strings), size)
    return header + PREAMBLE.pack(path_span[0], path_span[1], 2, 0) + \
        bytes(preamble_rows) + bytes(row_rows) + bytes(strings)


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
                       "lines": entry[2], "preamble": entry[3],
                       "rows": entry[4]}, stream, indent=2)
    print("%s: 1 series token, 5 scalars, 4 rows, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
