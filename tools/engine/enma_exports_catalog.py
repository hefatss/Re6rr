"""Pack the 172 exported symbol names from the shipped Enma DLL into R6EEX.

    python tools/engine/enma_exports_catalog.py \
        --out build/tmp/enma_exports.r6eex

Names come from docs/recon/enma_api.json, derived from the PE export table of
Wg6Enma_Release_IDL0.dll. No DLL bytes are committed.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "enma_api.json")

MAGIC = b"R6EEX\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    names = list(data["exports"])
    assert len(names) == 172
    assert len(set(names)) == len(names)
    assert all(name.isascii() and name for name in names)
    return names


def build(names):
    rows = names
    strings_off = HEADER.size + len(rows) * 4
    strings = bytearray()
    offsets = []
    for name in rows:
        offsets.append(strings_off + len(strings))
        strings.extend(name.encode("ascii") + b"\0")
    return (HEADER.pack(MAGIC, VERSION, len(rows), strings_off,
                        len(strings)) +
            b"".join(struct.pack("<I", offset) for offset in offsets) +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    names = collect(args.report)
    blob = build(names)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d exports, %d bytes" % (args.out, len(names), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
