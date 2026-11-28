r"""Pack shipped root setting.lua.gz structural facts.

    python tools/engine/setting_lua_gz_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/setting_lua_gz.r6slg

Paths, gzip header words, CRC32/ISIZE and copied ASCII key/integer rows are
packed. Compressed deflate bytes are not stored; no setting meaning is inferred.
"""

import argparse
import gzip
import glob
import json
import os
import re
import struct

MAGIC = b"R6SLG\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
FILE = struct.Struct("<6I")
SPAN = struct.Struct("<2I")
PATTERN = "*setting.lua.gz"
EXPECTED_FILES = 6
EXPECTED_BYTES = 2882
EXPECTED_INFLATED = 7258
EXPECTED_KEYS = 53
EXPECTED_LINES = 60
LINE = re.compile(r"^([A-Za-z_]\w*) = (-?\d+)$")
HEAD = bytes.fromhex("1f8b0800")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, "**", PATTERN),
                             recursive=True))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected setting.lua.gz corpus")
    files = []
    order = None
    for path in paths:
        raw = open(path, "rb").read()
        inflated = gzip.decompress(raw)
        if len(raw) < 18 or raw[:4] != HEAD or raw[3] != 0 or \
                raw[8] != 0 or raw[9] != 0xff or \
                struct.unpack_from("<I", raw, len(raw) - 4)[0] != len(inflated):
            raise ValueError("bad gzip envelope: " + path)
        text = inflated.decode("ascii")
        lines = text.splitlines()
        if len(lines) != EXPECTED_LINES or inflated.count(b"\n") != \
                EXPECTED_LINES or b"\r" in inflated:
            raise ValueError("bad setting.lua line shape: " + path)
        if lines[:3] != ["-" * 32, "---- setting.lua", "-" * 32] or \
                lines[-3:] != ["-" * 32, "---- EOF", "-" * 32] or lines[3]:
            raise ValueError("bad setting.lua frame: " + path)
        rows = []
        for line in lines[4:-3]:
            match = LINE.match(line)
            if not match:
                raise ValueError("bad setting.lua row: " + path)
            rows.append((match.group(1), match.group(2)))
        keys = [key for key, _ in rows]
        if len(rows) != EXPECTED_KEYS or (order and keys != order):
            raise ValueError("unexpected setting.lua key order: " + path)
        order = keys
        files.append((os.path.relpath(path, dump).replace("\\", "/"),
                      len(raw), struct.unpack_from("<I", raw, 4)[0],
                      struct.unpack_from("<I", raw, len(raw) - 8)[0],
                      len(inflated), rows))
    if sum(row[4] for row in files) != EXPECTED_INFLATED:
        raise ValueError("unexpected inflated total")
    return order, files


def build(keys, files):
    value_count = len(files) * len(keys)
    strings_base = HEADER.size + len(files) * FILE.size + \
        (len(keys) + value_count) * SPAN.size
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

    key_spans = bytearray()
    for key in keys:
        offset, length = add(key)
        key_spans.extend(SPAN.pack(offset, length))
    value_spans = bytearray()
    file_rows = bytearray()
    for path, size, mtime, crc, inflated_size, rows in files:
        offset, length = add(path)
        file_rows.extend(FILE.pack(offset, length, size, mtime, crc,
                                   inflated_size))
        for _, value in rows:
            offset, length = add(value)
            value_spans.extend(SPAN.pack(offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(keys),
                         len(strings), EXPECTED_BYTES, EXPECTED_INFLATED,
                         EXPECTED_LINES)
    return header + bytes(file_rows) + bytes(key_spans) + \
        bytes(value_spans) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    keys, files = collect(args.dump)
    blob = build(keys, files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"keys": keys, "files": [
                {"path": row[0], "bytes": row[1], "mtime": row[2],
                 "crc32": row[3], "inflated": row[4],
                 "values": [value for _, value in row[5]]}
                for row in files]}, stream, indent=2)
    print("%s: %d gzip files, %d keys, %d values, %d bytes" %
          (args.out, len(files), len(keys), len(files) * len(keys),
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
