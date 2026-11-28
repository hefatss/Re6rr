r"""Pack the shipped ytPhantomTempRun.bin fixed binary shape.

    python tools/engine/phantom_run_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/phantom_run.r6phm

The six header words, five u64 timestamps and 2,333 u64 records are copied
verbatim. No timestamp unit, record flag, count meaning or sample encoding is
inferred.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6PHM\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s11I")
WORD = struct.Struct("<Q")
RELATIVE = os.path.join("data", "Enma", "ytPhantomTempRun.bin")
EXPECTED_BYTES = 18728
EXPECTED_HEADER = (1573408, 1, 13, 21, 5, 311)
EXPECTED_TIMESTAMPS = (1724559025,) * 5
EXPECTED_RECORDS = 2333
DATA_BASE = 0x40


def collect(dump):
    path = os.path.join(dump, RELATIVE)
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES:
        raise ValueError("unexpected phantom run size")
    header = struct.unpack_from("<6I", raw, 0)
    timestamps = struct.unpack_from("<5Q", raw, 0x18)
    count = (len(raw) - DATA_BASE) // 8
    if header != EXPECTED_HEADER or timestamps != EXPECTED_TIMESTAMPS or \
            count != EXPECTED_RECORDS or (len(raw) - DATA_BASE) % 8:
        raise ValueError("unexpected phantom run layout")
    records = struct.unpack_from("<%dQ" % count, raw, DATA_BASE)
    return RELATIVE.replace("\\", "/"), len(raw), header, timestamps, records


def build(entry):
    path, size, header, timestamps, records = entry
    blob = bytearray(HEADER.pack(MAGIC, VERSION, 1, len(records),
                                 len(timestamps), size, *header))
    for value in timestamps:
        blob.extend(WORD.pack(value))
    for value in records:
        blob.extend(WORD.pack(value))
    return bytes(blob)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    entry = collect(args.dump)
    blob = build(entry)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"path": entry[0], "bytes": entry[1],
                       "header": entry[2], "timestamps": entry[3],
                       "records": entry[4]}, stream, indent=2)
    print("%s: 6 header words, 5 timestamps, 2333 records, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
