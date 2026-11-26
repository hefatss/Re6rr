"""Pack recovered Enma enum names into an R6EME blob.

    python tools/engine/enma_enum_catalog.py \
        --out build/tmp/enma_enums.r6eme

Names and integer values come from docs/recon/enma_api.json, derived by reading
the exported enum getters in Wg6Enma_Release_IDL0.dll. No dump data is committed.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "enma_api.json")

MAGIC = b"R6EME\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
ENUM = struct.Struct("<IIII")
VALUE = struct.Struct("<II")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    result = []
    for name in sorted(data["enums"]):
        values = [(int(value), symbol)
                  for value, symbol in data["enums"][name]]
        assert all(value >= 0 for value, _symbol in values)
        result.append({"name": name, "values": values})
    assert len(result) == 16, len(result)
    assert sum(len(item["values"]) for item in result) == 1214
    return result


def build(enums):
    arrays_base = HEADER.size + ENUM.size * len(enums)
    strings_off = arrays_base + sum(len(item["values"]) * 8
                                    for item in enums)
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("utf8") + b"\0")
        return offset

    names = [(item, add(item["name"])) for item in enums]
    arrays = bytearray()

    def alloc(item):
        offset = arrays_base + len(arrays)
        records = [(add(symbol), value) for value, symbol in item["values"]]
        arrays.extend(b"".join(VALUE.pack(name_off, value)
                               for name_off, value in records))
        return offset

    records = [(item, name_off, alloc(item)) for item, name_off in names]
    assert arrays_base + len(arrays) == strings_off

    payload = b""
    for item, name_off, values_off in records:
        payload += ENUM.pack(name_off, len(item["values"]), values_off, 0)
    return (HEADER.pack(MAGIC, VERSION, len(enums), strings_off,
                        len(strings)) + payload + bytes(arrays) +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    enums = collect(args.report)
    blob = build(enums)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d enums, %d names, %d bytes" %
          (args.out, len(enums), sum(len(item["values"]) for item in enums),
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
