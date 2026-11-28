r"""Pack shipped keyconfig.toml line facts.

    python tools/engine/keyconfig_toml_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/keyconfig_toml.r6key

Path and verbatim ASCII lines with blank/comment/active kinds are copied.
Key binding meaning and SDL token resolution stay unparsed.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6KEY\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
LINE = struct.Struct("<4I")
RELATIVE = "keyconfig.toml"
EXPECTED_BYTES = 1106
EXPECTED_LINES = 39
EXPECTED_ACTIVE = 22
EXPECTED_COMMENTS = 13
EXPECTED_BLANKS = 4


def collect(dump):
    path = os.path.join(dump, RELATIVE)
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\r\n") != EXPECTED_LINES:
        raise ValueError("unexpected keyconfig source")
    source = raw.decode("ascii")
    rows = []
    for index, value in enumerate(source.splitlines(), 1):
        if not value:
            kind = 0
        elif value.startswith("#"):
            kind = 1
        else:
            kind = 2
        rows.append((value, kind, index))
    if sum(1 for row in rows if row[1] == 2) != EXPECTED_ACTIVE or \
            sum(1 for row in rows if row[1] == 1) != EXPECTED_COMMENTS or \
            sum(1 for row in rows if row[1] == 0) != EXPECTED_BLANKS:
        raise ValueError("unexpected keyconfig row shape")
    return RELATIVE, len(raw), len(rows), rows


def build(entry):
    path, size, lines, rows = entry
    strings_base = HEADER.size + len(rows) * LINE.size
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
    line_rows = bytearray()
    for value, kind, line in rows:
        span = add(value)
        line_rows.extend(LINE.pack(span[0], span[1], kind, line))
    header = HEADER.pack(MAGIC, VERSION, 1, len(rows), len(strings), size,
                         EXPECTED_ACTIVE, EXPECTED_COMMENTS,
                         EXPECTED_BLANKS, path_span[0], path_span[1])
    return header + bytes(line_rows) + bytes(strings)


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
    print("%s: 39 keyconfig lines, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
