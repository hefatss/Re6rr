r"""Pack layout facts from shipped Enma ytErrorLogMerge text tables.

    python tools/engine/enma_error_log_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/enma_error_log.r6elm

Line shapes, sizes, counts and distinct kind/tag counts are copied. Odo, T,
speed, Yrot and AZThre numbers are not copied.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6ELM\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<9I")
EXPECTED_FILES = 6
EXPECTED_BYTES = 448033
EXPECTED_LINES = 4010
SECTOR = re.compile(
    rb"^<([A-Za-z]+) / (\d+)> T=\d+\.\d{6}, \(first,last\)=(\d+),(\d+) "
    rb"\(AZThre: \d+\.\d{6}\)$")
VECTOR = re.compile(
    rb"^Odo:\d+\.\d{6} <[A-Za-z]+ / \d+> az,px="
    rb"\(\d+\.\d{6},-?\d+\.\d{6}\) / T:\d+\.\d{6} "
    rb"speed:\d+\.\d{6} / Yrot:-?\d+\.\d{6} $")
TAG = re.compile(rb"<([A-Za-z]+) / \d+>")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(
        dump, "data", "Enma", "ytErrorLogMerge*.txt")))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d error log files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    names = {}
    for path in paths:
        raw = open(path, "rb").read()
        name = os.path.basename(path)
        shape = 0 if name.endswith("Sector.txt") else 1
        pattern = SECTOR if shape == 0 else VECTOR
        lines = raw.split(b"\r\n")
        if lines and not lines[-1]:
            lines.pop()
        if raw.count(b"\r\n") != len(lines):
            raise ValueError("non-CRLF line ending: %s" % path)
        tokens = set()
        lengths = []
        last = 0
        for line in lines:
            match = pattern.match(line)
            if not match or any(byte >= 0x80 for byte in line):
                raise ValueError("bad error log line: %s" % path)
            tokens.add(TAG.search(line).group(1))
            lengths.append(len(line))
            if shape == 0:
                last = int(match.group(4))
        names[name[:-4]] = (shape, len(lines), last)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), len(lines), shape, min(lengths), max(lengths),
                     len(lines), len(tokens)))
    for base, (shape, lines, last) in names.items():
        if shape == 0 and names[base[:-6] + "Vec"][1] != last + 2:
            raise ValueError("sector/vector line mismatch: %s" % base)
    if sum(row[1] for row in rows) != EXPECTED_BYTES or \
            sum(row[2] for row in rows) != EXPECTED_LINES:
        raise ValueError("unexpected error log corpus totals")
    return rows


def build(rows):
    strings_base = HEADER.size + len(rows) * FILE.size
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
    for row in rows:
        path_offset, path_length = add(row[0])
        file_rows.extend(FILE.pack(path_offset, path_length, *row[1:]))
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(strings),
        sum(row[1] for row in rows), sum(row[2] for row in rows),
        sum(row[2] for row in rows),
        sum(row[2] for row in rows if row[3] == 0),
        sum(row[2] for row in rows if row[3] == 1),
        sum(row[3] == 0 for row in rows))
    return header + bytes(file_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    rows = collect(args.dump)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump([{"path": row[0], "bytes": row[1],
                        "lines": row[2], "shape": row[3],
                        "line_lengths": (row[4], row[5]),
                        "tokens": row[7]} for row in rows],
                      stream, indent=2)
    print("%s: %d error logs, %d lines, %d bytes" %
          (args.out, len(rows), sum(row[2] for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
