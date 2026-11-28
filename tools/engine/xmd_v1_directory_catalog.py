r"""Pack shipped XMD version 0/1 stream directory facts.

    python tools/engine/xmd_v1_directory_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/xmd_v1_directory.r6xd1

Source paths, container sizes, version/count words, stream offsets and the
first eight bytes of each stream are copied. Stream payloads are not parsed.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6XD1\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<7I")
STREAM = struct.Struct("<2I8s")
EXPECTED_FILES = 3
EXPECTED_STREAMS = 30
EXPECTED_BYTES = 527072


def scan(dump):
    rows = []
    for root, _, files in os.walk(dump):
        for name in files:
            path = os.path.join(root, name)
            try:
                with open(path, "rb") as stream:
                    head = stream.read(16)
            except OSError:
                continue
            if head[:8] != b"XMD\x00001\x00":
                continue
            version, count = struct.unpack_from("<II", head, 8)
            if version > 1:
                continue
            with open(path, "rb") as stream:
                raw = stream.read()
            rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                         raw, version, count))
    rows.sort(key=lambda row: row[0])
    if len(rows) != EXPECTED_FILES or \
            sum(len(row[1]) for row in rows) != EXPECTED_BYTES:
        raise ValueError("unexpected XMD version 0/1 corpus")
    return rows


def collect(dump):
    files = []
    streams = []
    for path, raw, version, count in scan(dump):
        table_end = 16 + count * 4
        if len(raw) < table_end:
            raise ValueError("short XMD offset table: " + path)
        offsets = struct.unpack_from("<%dI" % count, raw, 16)
        if list(offsets) != sorted(offsets) or \
                any(offset < table_end or offset > len(raw)
                    for offset in offsets):
            raise ValueError("bad XMD offsets: " + path)
        rows = []
        for index, offset in enumerate(offsets):
            end = offsets[index + 1] if index + 1 < count else len(raw)
            if end < offset or end > len(raw):
                raise ValueError("bad XMD stream span: " + path)
            rows.append((offset, end - offset, raw[offset:offset + 8]))
        files.append((path, len(raw), version, table_end, len(streams),
                      rows))
        streams.extend(rows)
    if len(streams) != EXPECTED_STREAMS:
        raise ValueError("unexpected XMD stream total")
    return files


def build(files):
    rows = [row for entry in files for row in entry[5]]
    strings_base = HEADER.size + len(files) * FILE.size + \
        len(rows) * STREAM.size
    strings = bytearray()
    offsets = {}
    path_offsets = []
    for path, size, version, table_end, stream_index, _ in files:
        raw = path.encode("ascii")
        found = offsets.get(raw)
        if found is None:
            found = strings_base + len(strings)
            offsets[raw] = found
            strings.extend(raw + b"\0")
        path_offsets.append((found, len(raw)))
    file_rows = bytearray()
    stream_rows = bytearray()
    for (_, size, version, table_end, stream_index, stream_rows_data), span in \
            zip(files, path_offsets):
        file_rows.extend(FILE.pack(span[0], span[1], size, version,
                                   table_end, stream_index,
                                   len(stream_rows_data)))
        for offset, length, magic in stream_rows_data:
            stream_rows.extend(STREAM.pack(offset, length,
                                           magic[:8].ljust(8, b"\0")))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(rows),
                         len(strings), EXPECTED_BYTES)
    return header + bytes(file_rows) + bytes(stream_rows) + bytes(strings)


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
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump([{"path": row[0], "bytes": row[1], "version": row[2],
                        "table_end": row[3],
                        "streams": [{"offset": item[0], "bytes": item[1],
                                     "magic": item[2].hex()}
                                    for item in row[5]]}
                       for row in files], stream, indent=2)
    print("%s: %d XMD files, %d streams, %d bytes" %
          (args.out, len(files), sum(len(row[5]) for row in files), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
