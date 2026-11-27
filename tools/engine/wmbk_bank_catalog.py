r"""Pack structural facts from root FBK/GBK_W6W gzip banks.

    python tools/engine/wmbk_bank_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/wmbk_bank.r6wbk

Each bank inflates to a sequence of `WMBK` records. Paths, gzip header words,
record headers and byte spans are copied; payload u32 words are not decoded.
"""

import argparse
import glob
import gzip
import json
import os
import struct

MAGIC = b"R6WBK\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<11I")
RECORD = struct.Struct("<5I")
EXPECTED_FILES = 20
EXPECTED_RECORDS = 22
EXPECTED_PAIRS = 10
RECORD_MAGIC = b"WMBK"
RECORD_MAGIC_U32 = struct.unpack("<I", RECORD_MAGIC)[0]
RECORD_VERSION = 1
MIN_PAYLOAD = 12
GZIP_MAGIC = b"\x1f\x8b"


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, "FBK_W6W_*.bin")) +
                   glob.glob(os.path.join(dump, "GBK_W6W_*.bin")))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d WMBK banks, found %d" %
                         (EXPECTED_FILES, len(paths)))
    files = []
    records = []
    pairs = {}
    for path in paths:
        raw = open(path, "rb").read()
        if len(raw) < 18 or raw[:2] != GZIP_MAGIC or raw[2] != 8 or \
                raw[3] != 0 or raw[8] != 0 or raw[9] != 255:
            raise ValueError("unexpected gzip header: %s" % path)
        mtime = struct.unpack_from("<I", raw, 4)[0]
        isize = struct.unpack_from("<I", raw, len(raw) - 4)[0]
        inflated = gzip.decompress(raw)
        if len(inflated) != isize:
            raise ValueError("gzip ISIZE mismatch: %s" % path)
        at = 0
        rows = []
        while at < len(inflated):
            if inflated[at:at + 4] != RECORD_MAGIC:
                raise ValueError("bad WMBK magic at %d: %s" % (at, path))
            version, payload = struct.unpack_from("<HH", inflated, at + 4)
            if version != RECORD_VERSION or payload < MIN_PAYLOAD:
                raise ValueError("bad WMBK header at %d: %s" % (at, path))
            size = 8 + payload
            if at + size > len(inflated):
                raise ValueError("short WMBK record: %s" % path)
            rows.append((at, RECORD_MAGIC_U32, version, payload))
            at += size
        if at != len(inflated) or not rows:
            raise ValueError("incomplete WMBK stream: %s" % path)
        name = os.path.basename(path)
        if not (name.startswith("FBK_W6W_") or
                name.startswith("GBK_W6W_")) or not name.endswith(".bin"):
            raise ValueError("unexpected bank name: %s" % name)
        suffix = name[8:-4]
        others = pairs.setdefault(suffix, {})
        kind = name[:3]
        if kind in others:
            raise ValueError("duplicate bank pair: %s" % name)
        others[kind] = inflated
        files.append((os.path.relpath(path, dump).replace("\\", "/"),
                      len(raw), len(inflated), mtime, isize,
                      raw[3], raw[8], raw[9], rows))
    if len(pairs) != EXPECTED_PAIRS or any(
            set(pair) != {"FBK", "GBK"} or pair["FBK"] != pair["GBK"]
            for pair in pairs.values()):
        raise ValueError("FBK/GBK inflated bytes disagree")
    return files


def build(files):
    strings_base = HEADER.size + len(files) * FILE.size + \
        sum(len(row[8]) for row in files) * RECORD.size
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
    record_rows = bytearray()
    record_index = 0
    compressed_total = 0
    inflated_total = 0
    for path, compressed, inflated, mtime, isize, flg, xfl, os_byte, rows in files:
        offset, length = add(path)
        file_rows.extend(FILE.pack(offset, length, compressed, inflated,
                                   mtime, isize, record_index, len(rows),
                                   flg, xfl, os_byte))
        for byte_offset, magic, version, payload in rows:
            record_rows.extend(RECORD.pack(len(file_rows) // FILE.size - 1,
                                           byte_offset, magic, version, payload))
            record_index += 1
        compressed_total += compressed
        inflated_total += inflated
    header = HEADER.pack(MAGIC, VERSION, len(files), record_index,
                         len(strings), compressed_total, inflated_total)
    return header + bytes(file_rows) + bytes(record_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files = collect(args.dump)
    blob = build(files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump([{"path": row[0], "compressed": row[1],
                        "inflated": row[2], "mtime": row[3],
                        "records": row[8]} for row in files], stream, indent=2)
    print("%s: %d banks, %d records, %d bytes" %
          (args.out, len(files), sum(len(row[8]) for row in files), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
