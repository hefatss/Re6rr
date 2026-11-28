r"""Pack root auxiliary gzip envelope facts.

    python tools/engine/root_gz_envelope_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/root_gz_envelope.r6rgz

File names, compressed sizes, gzip header words, CRC32/ISIZE and empty-file
flags are copied. Inflated payloads and setting.lua.gz files are excluded; no
log, revision or authentication meaning is inferred.
"""

import argparse
import gzip
import glob
import json
import os
import struct

MAGIC = b"R6RGZ\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<8I")
EXPECTED_FILES = 25
EXPECTED_VALID = 20
EXPECTED_EMPTY = 5
EXPECTED_SOURCE = 1239
HEAD = bytes.fromhex("1f8b0800")


def collect(dump):
    paths = sorted(path for path in glob.glob(os.path.join(dump, "*.gz"))
                   if not path.endswith("setting.lua.gz"))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_SOURCE:
        raise ValueError("unexpected root gzip corpus")
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        name = os.path.basename(path)
        if not raw:
            rows.append((name, 0, 0, 0, 0, 0, 0))
            continue
        if len(raw) < 18 or raw[:4] != HEAD or raw[8] != 0 or \
                raw[9] != 0xff:
            raise ValueError("bad gzip envelope: " + name)
        inflated = gzip.decompress(raw)
        crc, isize = struct.unpack_from("<II", raw, len(raw) - 8)
        if crc != zlib_crc(inflated) or isize != len(inflated):
            raise ValueError("bad gzip trailer: " + name)
        rows.append((name, len(raw), struct.unpack_from("<I", raw, 4)[0],
                     crc, isize, raw[3], 1))
    if sum(row[6] for row in rows) != EXPECTED_VALID or \
            sum(1 for row in rows if not row[6]) != EXPECTED_EMPTY:
        raise ValueError("unexpected root gzip shape")
    return rows


def zlib_crc(raw):
    import zlib
    return zlib.crc32(raw) & 0xffffffff


def build(rows):
    strings_base = HEADER.size + len(rows) * FILE.size
    strings = bytearray()
    offsets = {}
    for name, *_ in rows:
        raw = name.encode("ascii")
        if raw in offsets:
            continue
        offsets[raw] = strings_base + len(strings)
        strings.extend(raw + b"\0")
    file_rows = bytearray()
    for name, size, mtime, crc, isize, header, valid in rows:
        raw = name.encode("ascii")
        file_rows.extend(FILE.pack(offsets[raw], len(raw), size, mtime,
                                   crc, isize, header, valid))
    header = HEADER.pack(MAGIC, VERSION, len(rows), EXPECTED_VALID,
                         EXPECTED_EMPTY, EXPECTED_SOURCE, len(strings))
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
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump(rows, stream, indent=2)
    print("%s: 25 gzip envelopes, 20 valid, 5 empty, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
