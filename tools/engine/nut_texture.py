"""Inventory shipped `.nut` texture containers without storing texture data.

    python tools/engine/nut_texture.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/nut_texture.json

Containers are either gzip-wrapped or raw NTWD/NTLX. NTWD has a 0x10-byte
prefix followed by 0x50-byte per-entry descriptors; each entry has a payload
whose size is stored at +0x18. Declarations here are layout facts observed in
the shipped files; pixel-format semantics are not inferred.

"""

import argparse
import gzip
import json
import os
import struct

NTWD = b"NTWD"
NTLX = b"NTLX"
GZIP = b"\x1f\x8b"
DESCRIPTOR_SIZE = 0x50
PREFIX_SIZE = 0x10
GIDX_OFFSET = 0x30


def parse_nut(path):
    """Return NTWD/NTLX header layout metadata for one shipped file."""
    with open(path, "rb") as stream:
        raw = stream.read()
    compressed = raw[:2] == GZIP
    if compressed:
        raw = gzip.decompress(raw)
    result = {"path": os.path.relpath(path).replace("\\", "/"),
              "compressed": compressed, "size": len(raw)}
    if raw[:4] == NTLX:
        result.update({"container": "NTLX",
                       "version": struct.unpack_from("<H", raw, 4)[0],
                       "entries": struct.unpack_from("<H", raw, 6)[0]})
        return result
    if raw[:4] != NTWD:
        raise ValueError("unknown .nut container: %s" % path)
    version, entries = struct.unpack_from("<HH", raw, 4)
    total, payload_size, descriptor_size = struct.unpack_from("<QII", raw,
                                                              0x10)
    packed0, packed1 = struct.unpack_from("<II", raw, 0x20)
    gidx = struct.unpack_from("<Q", raw, GIDX_OFFSET)[0]
    payload_offset = PREFIX_SIZE + entries * DESCRIPTOR_SIZE
    result.update({
        "container": "NTWD", "version": version, "entries": entries,
        "total": total, "payload_size": payload_size,
        "descriptor_size": descriptor_size,
        "packed0": (packed0 & 0xffff, packed0 >> 16),
        "dimensions": (packed1 & 0xffff, packed1 >> 16),
        "gidx": gidx, "payload_offset": payload_offset,
        "exact": len(raw) == payload_offset + entries * payload_size,
    })
    return result


def nut_payload(path):
    """Return the first entry's payload bytes from an NTWD container."""
    with open(path, "rb") as stream:
        raw = stream.read()
    if raw[:2] == GZIP:
        raw = gzip.decompress(raw)
    if raw[:4] != NTWD:
        raise ValueError("not an NTWD container: %s" % path)
    entries = struct.unpack_from("<H", raw, 6)[0]
    payload_size = struct.unpack_from("<I", raw, 0x18)[0]
    offset = PREFIX_SIZE + entries * DESCRIPTOR_SIZE
    return raw[offset:offset + payload_size]


def collect(dump):
    rows = []
    for directory, _, files in os.walk(dump):
        for name in files:
            if name.lower().endswith(".nut"):
                rows.append(parse_nut(os.path.join(directory, name)))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", help="write JSON report")
    args = parser.parse_args()
    rows = collect(args.dump)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf8") as stream:
            json.dump({"files": rows}, stream, indent=2)
    ntwd = [row for row in rows if row["container"] == "NTWD"]
    print("%d .nut files: %d NTWD (%d gzip), %d NTLX, %d exact layouts" %
          (len(rows), len(ntwd), sum(row["compressed"] for row in ntwd),
           len(rows) - len(ntwd), sum(row.get("exact", False) for row in ntwd)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
