r"""Pack root INI section/key structure without copying values.

    python tools/engine/root_ini_keys_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/root_ini_keys.r6rik

Two root INI files are reduced to section names, key names, line positions,
value-presence flags and section indices. Raw values, including identifiers,
are deliberately not copied.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6RIK\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<5I")
LINE = struct.Struct("<6I")
PATHS = ("card.ini", "teknoparrot.ini")
EXPECTED_BYTES = (63, 715)
EXPECTED_LINES = (3, 36)
EXPECTED_CRLF = (3, 33)
EXPECTED_TOTAL = 778
EXPECTED_SECTIONS = 8
EXPECTED_KEYS = 31


def collect(dump):
    files = []
    lines = []
    section = 0
    for relative, size, count, crlf in zip(PATHS, EXPECTED_BYTES,
                                           EXPECTED_LINES, EXPECTED_CRLF):
        path = os.path.join(dump, relative)
        raw = open(path, "rb").read()
        if len(raw) != size or raw.count(b"\r\n") != crlf:
            raise ValueError("unexpected root INI source: " + relative)
        rows = raw.decode("ascii").splitlines()
        base = len(lines)
        for offset, value in enumerate(rows, 1):
            number = base + offset
            if not value:
                kind, name, present = 0, "", 0
            elif value.startswith("[") and value.endswith("]") and len(value) > 2:
                kind, name, present = 1, value[1:-1], 0
                section += 1
            elif "=" in value:
                key, _, raw_value = value.partition("=")
                kind, name = 2, key.strip()
                present = 1 if raw_value.strip() else 0
            else:
                raise ValueError("unexpected root INI line: " + relative)
            lines.append((name, kind, number, present, section - 1))
        files.append((relative, size, count, base))
    if sum(row[1] for row in files) != EXPECTED_TOTAL or \
            sum(1 for row in lines if row[1] == 1) != EXPECTED_SECTIONS or \
            sum(1 for row in lines if row[1] == 2) != EXPECTED_KEYS:
        raise ValueError("unexpected root INI shape")
    return files, lines


def build(files, lines):
    strings_base = HEADER.size + len(files) * FILE.size + len(lines) * LINE.size
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

    file_rows = bytearray()
    for path, size, count, base in files:
        span = add(path)
        file_rows.extend(FILE.pack(span[0], span[1], size, count, base))
    empty = add("")
    line_rows = bytearray()
    for name, kind, number, present, section in lines:
        span = empty if not name else add(name)
        line_rows.extend(LINE.pack(span[0], span[1], kind, number,
                                   present, section))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(lines),
                         len(strings), EXPECTED_TOTAL)
    return header + bytes(file_rows) + bytes(line_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, lines = collect(args.dump)
    blob = build(files, lines)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": files, "lines": lines}, stream, indent=2)
    print("%s: 2 INI files, 8 sections, 31 keys, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
