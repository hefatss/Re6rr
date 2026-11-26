"""Pack shipped raw string xrefs into an R6SXR blob.

    python tools/engine/string_xrefs_catalog.py \
        --out build/tmp/string_xrefs.r6sxr

Facts come from docs/recon/xrefs.json: scan totals and 195 name-to-RVA hits
with 222 instruction references, before Lua binding synthesis.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "xrefs.json")

MAGIC = b"R6SXR\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
NAME = struct.Struct("<3I")
RVA = struct.Struct("<I")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    assert data["instructions"] == 4885740
    assert data["string_refs"] == 51737
    assert data["strings"] == 336413
    assert data["names_requested"] == 219
    assert data["names_found"] == 195
    assert len(data["hits"]) == 195
    assert all(refs == sorted(refs) for refs in data["hits"].values())
    assert sum(len(refs) for refs in data["hits"].values()) == 222
    return data


def build(data):
    rva_off = HEADER.size + NAME.size * len(data["hits"])
    strings_off = rva_off + sum(len(refs) for refs in data["hits"].values()) * RVA.size
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    first = 0
    name_payload = bytearray()
    rva_payload = bytearray()
    for name, refs in data["hits"].items():
        name_payload.extend(NAME.pack(add(name), first, len(refs)))
        for rva in refs:
            rva_payload.extend(RVA.pack(rva))
        first += len(refs)

    header = HEADER.pack(
        MAGIC, VERSION, data["instructions"], data["string_refs"],
        data["strings"], data["names_requested"], data["names_found"],
        len(data["hits"]), first, len(strings), strings_off)
    return header + bytes(name_payload) + bytes(rva_payload) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    data = collect(args.report)
    blob = build(data)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: 195 names, 222 string xrefs, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
