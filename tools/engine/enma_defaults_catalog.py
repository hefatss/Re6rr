"""Pack recovered Enma SetDefault constant writes into an R6EDF blob.

    python tools/engine/enma_defaults_catalog.py \
        --out build/tmp/enma_defaults.r6edf

Struct names, field offsets and constant bytes come from docs/recon/enma_api.json,
derived by tracing SetDefault writes in Wg6Enma_Release_IDL0.dll. No dump data
is committed.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "enma_api.json")

MAGIC = b"R6EDF\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIII")
STRUCT = struct.Struct("<IIII")
FIELD = struct.Struct("<IIII")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    result = []
    for name in sorted(data["defaults"]):
        item = data["defaults"][name]
        fields = []
        for field in item["fields"]:
            payload = bytes.fromhex(field["hex"])
            assert len(payload) == field["size"]
            fields.append({"offset": field["offset"], "size": field["size"],
                           "bytes": payload})
        result.append({"name": name, "max_written": item["max_written"],
                       "fields": fields})
    assert len(result) == 32, len(result)
    assert sum(len(item["fields"]) for item in result) == 89
    return result


def build(structs):
    fields_off = HEADER.size + STRUCT.size * len(structs)
    field_count = sum(len(item["fields"]) for item in structs)
    data_off = fields_off + FIELD.size * field_count
    data_size = sum(field["size"] for item in structs
                    for field in item["fields"])
    strings_off = data_off + data_size
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("utf8") + b"\0")
        return offset

    names = [(item, add(item["name"])) for item in structs]
    data = bytearray()
    records = []
    for item, name_off in names:
        rows = []
        for field in item["fields"]:
            offset = data_off + len(data)
            data.extend(field["bytes"])
            rows.append((field["offset"], field["size"], offset))
        records.append((item, name_off, rows))
    assert data_off + len(data) == strings_off

    payload = b""
    for item, name_off, rows in records:
        payload += STRUCT.pack(name_off, item["max_written"], len(rows), 0)
    for _item, _name_off, rows in records:
        for offset, size, data_at in rows:
            payload += FIELD.pack(offset, size, data_at, 0)
    return (HEADER.pack(MAGIC, VERSION, len(structs), fields_off, data_off,
                        strings_off, len(strings)) + payload + bytes(data) +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    structs = collect(args.report)
    blob = build(structs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d structs, %d fields, %d constant bytes, %d bytes" %
          (args.out, len(structs), sum(len(item["fields"])
                                       for item in structs),
           sum(field["size"] for item in structs
               for field in item["fields"]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
