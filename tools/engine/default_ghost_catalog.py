r"""Pack fixed-stride record layout facts from default ghost tables.

    python tools/engine/default_ghost_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/default_ghost.r6gh

Paths, counts, code words and NUL-terminated name-length ranges are copied.
Ghost names, ids and trajectory words are not copied.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6GH\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s11I")
FILE = struct.Struct("<11I")
STRIDE = 136
NAME1_OFFSET = 0x08
NAME1_CAPACITY = 16
NAME2_OFFSET = 0x60
NAME2_CAPACITY = 28
TUPLE_A_OFFSET = 0x54
TUPLE_B_OFFSET = 0x80
EXPECTED_FILES = 9
EXPECTED_RECORDS = 69056
EXPECTED_BYTES = 9391616


def collect(dump):
    paths = sorted(glob.glob(os.path.join(
        dump, "data", "ghost", "default_ghost_*.bin")))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d default ghost files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        if len(raw) % STRIDE or not raw:
            raise ValueError("bad ghost table length: %s" % path)
        count = len(raw) // STRIDE
        code = struct.unpack_from("<I", raw, 4)[0]
        first = []
        second = []
        tuple_a = set()
        tuple_b = set()
        for index in range(count):
            record = raw[index * STRIDE:(index + 1) * STRIDE]
            for offset, capacity, values in (
                    (NAME1_OFFSET, NAME1_CAPACITY, first),
                    (NAME2_OFFSET, NAME2_CAPACITY, second)):
                field = record[offset:offset + capacity]
                end = field.find(b"\0")
                if end <= 0:
                    raise ValueError("bad ghost name field: %s #%d" %
                                     (path, index))
                values.append(end)
            tuple_a.add(struct.unpack_from("<3I", record, TUPLE_A_OFFSET))
            tuple_b.add(struct.unpack_from("<2I", record, TUPLE_B_OFFSET))
        if not code:
            raise ValueError("zero ghost code: %s" % path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), count, code, min(first), max(first),
                     min(second), max(second), len(tuple_a), len(tuple_b)))
    if sum(row[1] for row in rows) != EXPECTED_BYTES or \
            sum(row[2] for row in rows) != EXPECTED_RECORDS:
        raise ValueError("unexpected ghost corpus totals")
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
        MAGIC, VERSION, len(rows), len(strings), STRIDE,
        NAME1_OFFSET, NAME1_CAPACITY, NAME2_OFFSET, NAME2_CAPACITY,
        TUPLE_A_OFFSET, TUPLE_B_OFFSET,
        sum(row[2] for row in rows))
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
                        "records": row[2], "code": row[3],
                        "name1": (row[4], row[5]), "name2": (row[6], row[7]),
                        "tuple_counts": (row[8], row[9])} for row in rows],
                      stream, indent=2)
    print("%s: %d ghost tables, %d records, %d bytes" %
          (args.out, len(rows), sum(row[2] for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
