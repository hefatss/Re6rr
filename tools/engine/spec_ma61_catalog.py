r"""Pack uncataloged PLC_MA61_Specification.lua scalar row facts.

    python tools/engine/spec_ma61_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/spec_ma61.r6ma6

Path, table span, key names, verbatim scalar literals and comment presence are
copied. Physics/tune meaning, message-ID resolution, Japanese comments and
accessor bodies stay unparsed.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6MA6\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
ROW = struct.Struct("<7I")
RELATIVE = "data_jp/car/specification/PLC_MA61_Specification.lua"
EXPECTED_BYTES = 139729
EXPECTED_LINES = 3000
TABLE_START = 12
TABLE_END = 387
ROW_COUNT = 373
KEY = re.compile(
    r"^\t\t([A-Za-z_]\w*)\s*=\s*(\"[^\"]*\"|-?\d+(?:\.\d+)?),?"
    r"(?:\s*--(.*))?$")


def collect(dump):
    path = os.path.join(dump, *RELATIVE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\r\n") != EXPECTED_LINES:
        raise ValueError("unexpected MA61 specification source")
    lines = raw.decode("cp932", errors="replace").splitlines()
    if len(lines) != EXPECTED_LINES:
        raise ValueError("unexpected MA61 line count")
    rows = []
    for index, line in enumerate(lines, 1):
        match = KEY.match(line)
        if not match:
            continue
        key, literal, comment = match.groups()
        if literal.startswith('"'):
            if any(ord(ch) > 0x7e for ch in literal):
                kind, literal = 3, ""
            else:
                kind = 2
        elif "." in literal:
            kind = 1
        else:
            kind = 0
        rows.append((key, literal, kind, index, 1 if comment else 0))
    if len(rows) != ROW_COUNT:
        raise ValueError("unexpected MA61 row count")
    if sum(1 for row in rows if row[2] == 0) != 317 or \
            sum(1 for row in rows if row[2] == 1) != 2 or \
            sum(1 for row in rows if row[2] == 2) != 38 or \
            sum(1 for row in rows if row[2] == 3) != 16 or \
            sum(row[4] for row in rows) != 46:
        raise ValueError("unexpected MA61 row shape")
    return RELATIVE, len(raw), len(lines), rows


def build(entry):
    path, size, lines, rows = entry
    strings_base = HEADER.size + len(rows) * ROW.size
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
    row_rows = bytearray()
    for key, literal, kind, line, comment in rows:
        key_span = add(key)
        literal_span = add(literal)
        row_rows.extend(ROW.pack(key_span[0], key_span[1],
                                 literal_span[0], literal_span[1],
                                 kind, line, comment))
    header = HEADER.pack(MAGIC, VERSION, 1, len(rows), len(strings), size,
                         lines, TABLE_START, TABLE_END,
                         path_span[0], path_span[1])
    return header + bytes(row_rows) + bytes(strings)


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
                       "lines": entry[2], "rows": entry[3]}, stream, indent=2)
    print("%s: 373 scalar rows, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
