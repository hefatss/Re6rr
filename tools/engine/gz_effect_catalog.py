r"""Pack gzip header and inflated-prefix facts for stage effect files.

    python tools/engine/gz_effect_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/gz_effect.r6gef

Every data/effect/stage_effect/**/*.gz stream is decompressed to verify CRC
and ISIZE. The gzip header, compressed/inflated sizes and the first 16 inflated
bytes are copied. Container payloads are not parsed or copied.
"""

import argparse
import glob
import gzip
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

MAGIC = b"R6GEF\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
FILE = struct.Struct("<IIIIIIIIIII16s")
EXPECTED_FILES = 1087
EXPECTED_FLAG0 = 602
EXPECTED_FLAG8 = 485
EXPECTED_KNOWN = 899
EXPECTED_OTHER = 188
KNOWN_MAGICS = (b"NDWD", b"NTWD", b"NDLX", b"NTLX")
PREFIX_SIZE = 16


def gzip_header(raw):
    if len(raw) < 18 or raw[:2] != b"\x1f\x8b" or raw[2] != 8:
        raise ValueError("bad gzip header")
    flags = raw[3]
    if flags & 0xE0:
        raise ValueError("reserved gzip flags")
    mtime = struct.unpack_from("<I", raw, 4)[0]
    xfl = raw[8]
    operating_system = raw[9]
    at = 10
    if flags & 4:
        if at + 2 > len(raw) - 8:
            raise ValueError("truncated gzip extra field")
        extra = struct.unpack_from("<H", raw, at)[0]
        at += 2 + extra
        if at > len(raw) - 8:
            raise ValueError("bad gzip extra field")
    for bit in (8, 16):
        if flags & bit:
            end = raw.find(b"\0", at, len(raw) - 8)
            if end < 0:
                raise ValueError("unterminated gzip text field")
            at = end + 1
    if flags & 2:
        at += 2
    if at + 8 > len(raw):
        raise ValueError("gzip header overlaps trailer")
    return flags, mtime, xfl, operating_system, at


def collect(dump):
    root = os.path.join(dump, "data", "effect", "stage_effect")
    paths = sorted(glob.glob(os.path.join(root, "**", "*.gz"),
                             recursive=True))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d stage effect gz files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    flags0 = flags8 = known = other = 0
    for path in paths:
        with open(path, "rb") as stream:
            raw = stream.read()
        flags, mtime, xfl, operating_system, header_size = gzip_header(raw)
        inflated = gzip.decompress(raw)
        isize = struct.unpack_from("<I", raw, len(raw) - 4)[0]
        if isize != len(inflated) or not inflated:
            raise ValueError("bad gzip ISIZE: %s" % path)
        prefix = inflated[:PREFIX_SIZE]
        prefix_length = len(prefix)
        prefix = prefix.ljust(PREFIX_SIZE, b"\0")
        if inflated[:4] in KNOWN_MAGICS:
            known += 1
        else:
            other += 1
        if flags == 0:
            flags0 += 1
        elif flags == 8:
            flags8 += 1
        else:
            raise ValueError("unexpected gzip flags %d: %s" % (flags, path))
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), flags, mtime, xfl, operating_system,
                     isize, len(inflated), header_size, prefix_length,
                     prefix))
    if (flags0, flags8, known, other) != (EXPECTED_FLAG0, EXPECTED_FLAG8,
                                         EXPECTED_KNOWN, EXPECTED_OTHER):
        raise ValueError("unexpected gzip class counts %d/%d/%d/%d" %
                         (flags0, flags8, known, other))
    return rows


def build(rows):
    strings = bytearray()
    paths = bytearray()
    strings_offset = HEADER.size + len(rows) * FILE.size
    for (path, compressed, flags, mtime, xfl, operating_system, isize,
         inflated, header_size, prefix_length, prefix) in rows:
        raw = path.encode("ascii")
        offset = strings_offset + len(strings)
        strings.extend(raw + b"\0")
        paths.extend(FILE.pack(offset, len(raw), compressed, flags, mtime,
                               xfl, operating_system, isize, inflated,
                               header_size, prefix_length, prefix))
    header = HEADER.pack(MAGIC, VERSION, len(rows), len(strings),
                         EXPECTED_FLAG0, EXPECTED_FLAG8, EXPECTED_KNOWN,
                         EXPECTED_OTHER)
    return header + bytes(paths) + bytes(strings)


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
            json.dump([{"path": row[0], "compressed": row[1],
                        "inflated": row[7], "prefix": row[10].hex()}
                       for row in rows], stream, indent=2)
    print("%s: %d stage effect gzip headers, %d bytes" %
          (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
