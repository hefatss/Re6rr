r"""Pack AMCUS INI section/key structure without copying values.

    python tools/engine/amcus_ini_keys_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/amcus_ini_keys.r6aik

Three AMCUS INI files are reduced to section names, key names, line kinds,
line positions, value-presence flags and section indices. Raw values, CP932
comment text and auth behavior stay uncopied.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6AIK\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
FILE = struct.Struct("<5I")
LINE = struct.Struct("<6I")
PATHS = ("AMCUS/AMConfig.ini", "AMCUS/AMConfig.ini.orig",
         "AMCUS/WritableConfig.ini")
EXPECTED_BYTES = (2426, 2518, 195)
EXPECTED_LINES = (96, 98, 10)
EXPECTED_SOURCE = 5139
EXPECTED_TOTAL = 204
EXPECTED_SECTIONS = 22
EXPECTED_KEYS = 139
EXPECTED_COMMENTS = 23
EXPECTED_BLANKS = 20


def collect(dump):
    files = []
    lines = []
    section = 0
    for relative, size, count in zip(PATHS, EXPECTED_BYTES, EXPECTED_LINES):
        path = os.path.join(dump, *relative.split("/"))
        raw = open(path, "rb").read()
        if len(raw) != size or raw.count(b"\r\n") != count:
            raise ValueError("unexpected AMCUS INI source: " + relative)
        rows = raw.split(b"\r\n")
        if len(rows) != count + 1:
            raise ValueError("unexpected AMCUS INI row count: " + relative)
        base = len(lines)
        for offset, value in enumerate(rows[:-1], 1):
            number = base + offset
            if not value:
                kind, name, present = 0, "", 0
            elif value.startswith(b";;"):
                kind, name, present = 1, "", 0
            elif value.lstrip().startswith(b"[") and \
                    value.rstrip().endswith(b"]"):
                raw_name = value.strip()[1:-1]
                kind = 2
                name = raw_name.decode("ascii")
                present = 0
                section += 1
            elif b"=" in value:
                raw_key = value.partition(b"=")[0].strip()
                kind = 3
                name = raw_key.decode("ascii")
                present = 1 if value.partition(b"=")[2].strip() else 0
            else:
                raise ValueError("unexpected AMCUS INI line %d: %s" %
                                 (number, relative))
            lines.append((name, kind, number, present, section - 1))
        files.append((relative, size, count, base))
    if sum(file[1] for file in files) != EXPECTED_SOURCE or \
            sum(file[2] for file in files) != EXPECTED_TOTAL or \
            sum(1 for line in lines if line[1] == 2) != EXPECTED_SECTIONS or \
            sum(1 for line in lines if line[1] == 3) != EXPECTED_KEYS or \
            sum(1 for line in lines if line[1] == 1) != EXPECTED_COMMENTS or \
            sum(1 for line in lines if line[1] == 0) != EXPECTED_BLANKS:
        raise ValueError("unexpected AMCUS INI shape")
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
                         len(strings), EXPECTED_SOURCE, EXPECTED_SECTIONS,
                         EXPECTED_KEYS, EXPECTED_COMMENTS, EXPECTED_BLANKS, 0)
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
    print("%s: 3 files, 22 sections, 139 keys, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
