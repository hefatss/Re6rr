r"""Pack shipped gamecontrollerdb.txt line and row facts.

    python tools/engine/sdl_db_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/sdl_db.r6sdl

Paths, line kinds, verbatim ASCII lines, id/name/platform spans and field
counts are copied. Device identity, SDL button meaning, platform priority and
remap behavior stay unparsed.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6SDL\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
LINE = struct.Struct("<4I")
ROW = struct.Struct("<8I")
RELATIVE = "gamecontrollerdb.txt"
EXPECTED_BYTES = 506637
EXPECTED_LINES = 1916
EXPECTED_ROWS = 1904
EXPECTED_COMMENTS = 7
EXPECTED_BLANKS = 5
ID = re.compile(r"^(?:[0-9a-fA-F]{32}|xinput)$")
PLATFORMS = ("platform:Windows", "platform:Linux", "platform:Android",
             "platform:Mac OS X", "platform:iOS")


def collect(dump):
    path = os.path.join(dump, RELATIVE)
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\r\n") != EXPECTED_LINES:
        raise ValueError("unexpected SDL database source")
    source = raw.decode("ascii")
    lines = source.splitlines()
    if len(lines) != EXPECTED_LINES:
        raise ValueError("unexpected SDL line count")
    line_rows = []
    row_rows = []
    for index, value in enumerate(lines, 1):
        if not value:
            kind = 0
        elif value.startswith("#"):
            kind = 1
        else:
            kind = 2
        line_rows.append((value, kind, index))
        if kind != 2:
            continue
        parts = value.split(",")
        if len(parts) < 7 or len(parts) > 30 or parts[-1] or \
                not ID.match(parts[0]) or parts[-2] not in PLATFORMS:
            raise ValueError("unexpected SDL row at line %d" % index)
        row_rows.append((parts[0], parts[1], parts[-2], len(parts), index))
    if len(row_rows) != EXPECTED_ROWS or \
            sum(1 for row in line_rows if row[1] == 1) != EXPECTED_COMMENTS or \
            sum(1 for row in line_rows if row[1] == 0) != EXPECTED_BLANKS:
        raise ValueError("unexpected SDL row shape")
    return RELATIVE, len(raw), len(lines), line_rows, row_rows


def build(entry):
    path, size, lines, line_rows, row_rows = entry
    strings_base = HEADER.size + len(line_rows) * LINE.size + \
        len(row_rows) * ROW.size
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
    line_records = bytearray()
    for value, kind, line in line_rows:
        span = add(value)
        line_records.extend(LINE.pack(span[0], span[1], kind, line))
    row_records = bytearray()
    for identity, name, platform, fields, line in row_rows:
        id_span = add(identity)
        name_span = add(name)
        platform_span = add(platform)
        row_records.extend(ROW.pack(id_span[0], id_span[1],
                                    name_span[0], name_span[1],
                                    platform_span[0], platform_span[1],
                                    fields, line))
    header = HEADER.pack(MAGIC, VERSION, 1, len(row_rows), len(line_rows),
                         len(strings), size, EXPECTED_COMMENTS,
                         EXPECTED_BLANKS, path_span[0], path_span[1])
    return header + bytes(line_records) + bytes(row_records) + bytes(strings)


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
                       "lines": entry[2], "rows": entry[4]}, stream, indent=2)
    print("%s: 1916 lines, 1904 rows, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
