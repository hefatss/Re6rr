r"""Pack structural row shapes from shipped filter dictionary Lua files.

    python tools/engine/filter_dictionary_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/filter_dictionary.r6flt

Line kinds, byte spans and true/false tokens are copied. Dictionary word
values are not copied and no filter semantics are inferred.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6FLT\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<11I")
ROW = struct.Struct("<6I")
EXPECTED_FILES = 17
EXPECTED_BYTES = 156169
EXPECTED_LINES = 6618
TABLE_RE = re.compile(rb"^Table\s*=")
BOOL_RE = re.compile(rb'^\{\s*".*",\s*(true|false)\s*\},')
KIND_TABLE = 0
KIND_OPEN = 1
KIND_CLOSE = 2
KIND_ACTIVE = 3
KIND_COMMENTED = 4
KIND_BOOL = 5
KIND_FUNCTION = 6


def classify(line):
    stripped = line.strip()
    if TABLE_RE.match(stripped):
        return KIND_TABLE, 2
    if stripped == b"{":
        return KIND_OPEN, 2
    if stripped == b"}":
        return KIND_CLOSE, 2
    match = BOOL_RE.match(stripped)
    if match:
        return KIND_BOOL, 1 if match.group(1) == b"true" else 0
    if stripped.startswith(b'"') and stripped.endswith(b'",'):
        return KIND_ACTIVE, 2
    if stripped.startswith(b"--"):
        rest = stripped.lstrip(b"-").strip()
        if rest.startswith(b'"') and rest.endswith(b'",'):
            return KIND_COMMENTED, 2
    if stripped.startswith(b"function"):
        return KIND_FUNCTION, 2
    return None


def collect(dump):
    root = os.path.join(dump, "data_jp", "filter")
    paths = sorted(glob.glob(os.path.join(root, "*.lua")))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d filter Lua files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    files = []
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        file_rows = []
        offset = 0
        for line_index, full in enumerate(raw.splitlines(keepends=True)):
            line = full.rstrip(b"\r\n")
            result = classify(line)
            if result is not None:
                kind, value = result
                file_rows.append((line_index, offset, len(line), kind, value))
            offset += len(full)
        if not file_rows:
            raise ValueError("no classified rows: %s" % path)
        counts = [0, 0, 0, 0, 0, 0, 0]
        for _, _, _, kind, _ in file_rows:
            counts[kind] += 1
        files.append((os.path.relpath(path, dump).replace("\\", "/"),
                      len(raw), len(raw.splitlines()), counts, file_rows))
        rows.extend(file_rows)
    assert sum(row[1] for row in files) == EXPECTED_BYTES
    assert sum(row[2] for row in files) == EXPECTED_LINES
    assert [sum(file[3][kind] for file in files)
            for kind in range(7)] == [16, 16, 16, 5949, 478, 13, 5]
    return files, rows


def build(files, rows):
    strings_base = HEADER.size + len(files) * FILE.size + \
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

    file_rows = bytearray()
    row_rows = bytearray()
    first = 0
    for path, source_size, line_count, counts, file_rows_local in files:
        offset, length = add(path)
        file_rows.extend(FILE.pack(offset, length, source_size, line_count,
                                   counts[KIND_ACTIVE], counts[KIND_COMMENTED],
                                   counts[KIND_BOOL], counts[KIND_TABLE],
                                   counts[KIND_FUNCTION], first,
                                   len(file_rows_local)))
        for line_index, byte_offset, line_length, kind, value in file_rows_local:
            row_rows.extend(ROW.pack(len(file_rows) // FILE.size - 1,
                                     line_index, byte_offset, line_length,
                                     kind, value))
        first += len(file_rows_local)
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows), len(strings),
                         sum(file[1] for file in files),
                         sum(file[2] for file in files))
    return header + bytes(file_rows) + bytes(row_rows) + bytes(strings)


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
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump([{"path": row[0], "bytes": row[1],
                        "lines": row[2], "counts": row[3]} for row in files],
                      stream, indent=2)
    print("%s: %d files, %d classified rows, %d bytes" %
          (args.out, len(files), len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
