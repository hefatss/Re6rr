r"""Pack shipped Enma trail header shapes without payload bytes.

    python tools/engine/trail_header_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/trail_header.r6th

File names, link counts, NUL-terminated ASCII link names, marker words, record
counts and trailer words are copied. The 52-byte records stay uncopied and
their semantics are not inferred.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6TH\0\1\0\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<10I")
NAME = struct.Struct("<3I")
PATHS = ("data/Enma/ytSamplingTempFile.trail", "data/Enma/ytTrailTempFile.trail")
EXPECTED_SIZES = (34414, 173250)
EXPECTED_LINKS = (1, 5)
EXPECTED_RECORDS = (661, 3330)
EXPECTED_TRAILERS = (0x00113aeb, 0x00536b19)
RECORD_SIZE = 52
HEAD_MAGIC = b"j1p\x01"
MARKER = b"u*7k"
MARKER_WORD = 3


def collect(dump):
    files = []
    names = []
    for index, (relative, size) in enumerate(zip(PATHS, EXPECTED_SIZES)):
        path = os.path.join(dump, *relative.split("/"))
        raw = open(path, "rb").read()
        if len(raw) != size or raw[:4] != HEAD_MAGIC:
            raise ValueError("unexpected trail header: " + relative)
        links = struct.unpack_from("<I", raw, 4)[0]
        if links != EXPECTED_LINKS[index]:
            raise ValueError("unexpected trail link count: " + relative)
        cursor = 8
        file_names = []
        for slot in range(links + 1):
            end = raw.index(b"\0", cursor)
            value = raw[cursor:end]
            if not value or any(byte < 0x20 or byte > 0x7e
                                for byte in value):
                raise ValueError("unexpected trail name: " + relative)
            file_names.append((value, cursor, end - cursor))
            names.append((value.decode("ascii"), cursor, end - cursor))
            cursor = end + 1
        marker = cursor
        if raw[marker:marker + 4] != MARKER or \
                struct.unpack_from("<I", raw, marker + 4)[0] != MARKER_WORD or \
                struct.unpack_from("<I", raw, marker + 8)[0] != \
                EXPECTED_RECORDS[index]:
            raise ValueError("unexpected trail marker: " + relative)
        payload = marker + 12
        records = EXPECTED_RECORDS[index]
        trailer_at = payload + records * RECORD_SIZE
        if trailer_at + 4 != size:
            raise ValueError("unexpected trail payload size: " + relative)
        trailer = struct.unpack_from("<I", raw, trailer_at)[0]
        if trailer != EXPECTED_TRAILERS[index]:
            raise ValueError("unexpected trail trailer: " + relative)
        files.append((relative, size, links, len(file_names), marker,
                      records, trailer))
    return files, names


def build(files, names):
    base = HEADER.size + len(files) * FILE.size + len(names) * NAME.size
    strings = bytearray()
    offsets = {}

    def add(value):
        found = offsets.get(value)
        if found is not None:
            return found
        offset = base + len(strings)
        offsets[value] = offset
        strings.extend(value + b"\0")
        return offset

    file_rows = bytearray()
    name_base = 0
    for relative, size, links, count, marker, records, trailer in files:
        raw = relative.encode("ascii")
        span = add(raw)
        file_rows.extend(FILE.pack(span, len(raw), size, links, name_base,
                                   count, marker, MARKER_WORD, records,
                                   trailer))
        name_base += count
    name_rows = bytearray()
    for value, source_offset, length in names:
        raw = value.encode("ascii")
        span = add(raw)
        name_rows.extend(NAME.pack(span, len(raw), source_offset))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(names),
                         sum(entry[1] for entry in files),
                         sum(entry[5] for entry in files), RECORD_SIZE,
                         len(strings), MARKER_WORD, 0)
    return header + bytes(file_rows) + bytes(name_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, names = collect(args.dump)
    blob = build(files, names)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": files, "names": names}, stream, indent=2)
    print("%s: 2 trail files, 8 link names, %d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
