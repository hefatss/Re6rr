r"""Pack shipped setting_default.lua row facts.

    python tools/engine/setting_default_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/setting_default.r6std

Source path, m_* row names, active flags, SettingConst tokens and hex
literals are copied. Japanese comments and setting behavior are not decoded.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6STD\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<4I")
ROW = struct.Struct("<5I")
RELATIVE = "data/setting/setting_default.lua"
EXPECTED_BYTES = 1343
EXPECTED_LINES = 34
EXPECTED_ROWS = 13
ROW_PATTERN = re.compile(r"^\s*(--\s*)?(m_[A-Za-z0-9_]+)\s*=\s*([^;]+);")


def collect(dump):
    path = os.path.join(dump, *RELATIVE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\n") != EXPECTED_LINES:
        raise ValueError("unexpected setting default source")
    text = raw.decode("ascii", errors="replace")
    rows = []
    for line in text.splitlines():
        match = ROW_PATTERN.match(line)
        if not match:
            continue
        value = re.sub(r"\s+", " ", match.group(3)).strip()
        if any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in value):
            raise ValueError("non-ASCII setting default value")
        rows.append((match.group(2), 0 if match.group(1) else 1, value))
    if len(rows) != EXPECTED_ROWS or sum(row[1] for row in rows) != 12:
        raise ValueError("unexpected setting default rows")
    return RELATIVE, len(raw), len(text.splitlines()), rows


def build(entry):
    path, size, lines, rows = entry
    strings_base = HEADER.size + FILE.size + len(rows) * ROW.size
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
    for name, active, value in rows:
        name_span = add(name)
        value_span = add(value)
        row_rows.extend(ROW.pack(name_span[0], name_span[1],
                                 value_span[0], value_span[1], active))
    header = HEADER.pack(MAGIC, VERSION, 1, len(rows), len(strings), size,
                         lines)
    return header + FILE.pack(path_span[0], path_span[1], size, lines) + \
        bytes(row_rows) + bytes(strings)


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
    print("%s: 13 setting rows, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
