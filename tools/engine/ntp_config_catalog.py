r"""Pack shipped NTP config text facts.

    python tools/engine/ntp_config_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/ntp_config.r6ntp

Paths, sizes, line counts and verbatim ASCII lines with blank/comment/active
kinds are copied. Time-service behavior is not decoded.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6NTP\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<5I")
LINE = struct.Struct("<3I")
PATHS = ("data/etc/ntp.drive.conf", "data/etc/ntp.terminal.conf")
EXPECTED_BYTES = (713, 712)
EXPECTED_LINES = (31, 30)
EXPECTED_TOTAL = 1425


def collect(dump):
    files = []
    lines = []
    for relative, size, count in zip(PATHS, EXPECTED_BYTES, EXPECTED_LINES):
        path = os.path.join(dump, *relative.split("/"))
        raw = open(path, "rb").read()
        if len(raw) != size or raw.count(b"\n") != count:
            raise ValueError("unexpected NTP config: " + relative)
        text = raw.decode("ascii")
        rows = text.splitlines()
        if len(rows) != count:
            raise ValueError("unexpected NTP line count: " + relative)
        kinds = []
        for row in rows:
            if not row:
                kind = 0
            elif row.startswith("#"):
                kind = 1
            else:
                kind = 2
            kinds.append(kind)
        base = len(lines)
        lines.extend(zip(rows, kinds))
        files.append((relative, size, count, base, tuple(kinds)))
    if sum(row[1] for row in files) != EXPECTED_TOTAL:
        raise ValueError("unexpected NTP source total")
    return files, lines


def build(files, lines):
    strings_base = HEADER.size + len(files) * FILE.size + \
        len(lines) * LINE.size
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
    for path, size, count, base, _ in files:
        span = add(path)
        file_rows.extend(FILE.pack(span[0], span[1], size, count, base))
    line_rows = bytearray()
    empty = add("")
    for value, kind in lines:
        if value:
            span = add(value)
            line_rows.extend(LINE.pack(span[0], span[1], kind))
        else:
            line_rows.extend(LINE.pack(empty[0], 0, 0))
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
    print("%s: 2 NTP configs, 61 lines, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
