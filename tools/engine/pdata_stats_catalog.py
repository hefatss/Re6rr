"""Pack shipped .pdata statistics into an R6PDS blob.

    python tools/engine/pdata_stats_catalog.py \
        --out build/tmp/pdata_stats.r6pds

Facts come from docs/recon/pdata.json: seven size buckets and the twenty
largest functions with copied RVAs and unwind chain fields.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "pdata.json")

MAGIC = b"R6PDS\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s14I")
BUCKET = struct.Struct("<2I")
FUNC = struct.Struct("<10I")
WORD = struct.Struct("<I")


def hex_or_none(value):
    return int(value, 16) if value is not None else 0


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    buckets = list(data["size_histogram"].items())
    largest = data["largest"]
    assert len(buckets) == 7 and len(largest) == 20
    assert data["functions"] == 70377
    assert sum(count for _label, count in buckets) == 70377
    return data, buckets, largest


def build(data, buckets, largest):
    func_off = HEADER.size + BUCKET.size * len(buckets)
    strings_off = func_off + FUNC.size * len(largest)
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    bucket_payload = b"".join(
        BUCKET.pack(add(label), count) for label, count in buckets)
    func_payload = bytearray()
    for row in largest:
        chain = row["chain"] or {}
        func_payload.extend(FUNC.pack(
            row["begin"], row["end"], row["size"], add(row["section"]),
            row["unwind_rva"], 1 if row["leaf"] else 0, row["flags"],
            hex_or_none(chain.get("begin")), hex_or_none(chain.get("end")),
            hex_or_none(chain.get("unwind"))))
    header = HEADER.pack(
        MAGIC, VERSION, data["functions"], data["code_bytes"],
        data["text_bytes"], data["leaf"], data["chained"], data["with_eh"],
        data["min"], data["max"], data["median"], len(buckets),
        len(largest), len(strings), strings_off)
    return (header + bucket_payload + bytes(func_payload) + bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    data, buckets, largest = collect(args.report)
    blob = build(data, buckets, largest)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: 7 size buckets, 20 largest functions, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
