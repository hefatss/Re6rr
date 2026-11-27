r"""Pack file-level NTWD/NTLX header facts from shipped .nut containers.

    python tools/engine/nut_file_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/nut_files.r6ntf

Paths and copied header words are packed; texture payloads and pixel data are
not. The compressed flag records only gzip framing, not texture semantics.
"""

import argparse
import json
import os
import struct

from nut_texture import GZIP, NTWD, NTLX, read_nut

MAGIC = b"R6NTF\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s3I2Q2I")
FILE = struct.Struct("<19I")
EXPECTED_FILES = 11151
EXPECTED_NTWD = 11008
EXPECTED_NTLX = 143
EXPECTED_GZIP = 5574
EXPECTED_EXACT = 9599
DESCRIPTOR_SIZES = (0x50, 0x60, 0x70, 0x80)


def collect(dump):
    paths = []
    for directory, _, names in os.walk(dump):
        for name in names:
            if name.lower().endswith(".nut"):
                paths.append(os.path.join(directory, name))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d .nut files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in sorted(paths):
        raw = open(path, "rb").read()
        compressed = raw[:2] == GZIP
        data = read_nut(path)
        if len(data) < 0x30 or data[:4] not in (NTWD, NTLX):
            raise ValueError("bad .nut container: %s" % path)
        version, entries = struct.unpack_from("<HH", data, 4)
        total, payload_size, descriptor_size = struct.unpack_from(
            "<QII", data, 0x10)
        packed0, packed1 = struct.unpack_from("<II", data, 0x20)
        gidx = struct.unpack_from("<Q", data, 0x30)[0]
        offset = 0x10 + entries * descriptor_size
        if version not in (1, 2) or not entries or \
                descriptor_size not in DESCRIPTOR_SIZES or \
                total != payload_size + descriptor_size or \
                offset > len(data):
            raise ValueError("bad .nut header: %s" % path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), len(data), 1 if compressed else 0,
                     struct.unpack("<I", data[:4])[0], version, entries,
                     total, payload_size, descriptor_size, packed0, packed1,
                     gidx, offset,
                     1 if len(data) == offset + entries * payload_size else 0))
    counts = (
        sum(row[4] == struct.unpack("<I", NTWD)[0] for row in rows),
        sum(row[4] == struct.unpack("<I", NTLX)[0] for row in rows),
        sum(row[3] for row in rows),
        sum(row[-1] for row in rows),
    )
    if counts != (EXPECTED_NTWD, EXPECTED_NTLX, EXPECTED_GZIP,
                  EXPECTED_EXACT):
        raise ValueError("unexpected .nut corpus totals: %r" % (counts,))
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
    for path, source, inflated, compressed, container, version, entries, \
            total, payload, descriptor, packed0, packed1, gidx, offset, \
            exact in rows:
        path_offset, path_length = add(path)
        file_rows.extend(FILE.pack(
            path_offset, path_length, source, inflated, compressed,
            container, version, entries,
            total & 0xffffffff, total >> 32,
            payload, descriptor, packed0, packed1,
            gidx & 0xffffffff, gidx >> 32,
            offset & 0xffffffff, offset >> 32, exact))
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(strings),
        sum(row[1] for row in rows), sum(row[2] for row in rows),
        sum(row[3] for row in rows), sum(row[-1] for row in rows))
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
                        "inflated": row[2], "compressed": row[3],
                        "container": row[4].to_bytes(4, "little").decode(),
                        "entries": row[6], "exact": row[-1]}
                       for row in rows], stream, indent=2)
    print("%s: %d .nut headers, %d bytes" % (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
