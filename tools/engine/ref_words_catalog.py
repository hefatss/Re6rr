"""Pack shipped x64 reference-word xrefs into an R6REF blob.

    python tools/engine/ref_words_catalog.py \
        --out build/tmp/ref_words.r6ref

Facts come from docs/recon/refs.json: 98,805 distinct 32-bit operand words and
174,507 instruction RVAs that reference them. Negative hex keys are kept as
raw low-32 bit values and are not interpreted as addresses.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "refs.json")

MAGIC = b"R6REF\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s3I")
WORD = struct.Struct("<3I")
XREF = struct.Struct("<I")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    words = []
    for key, refs in data.items():
        value = int(key, 16) & 0xffffffff
        assert refs == sorted(refs)
        words.append((value, refs))
    words.sort()
    assert len(words) == 98805
    assert sum(len(refs) for _value, refs in words) == 174507
    return words


def build(words):
    xref_off = HEADER.size + WORD.size * len(words)
    first = 0
    word_payload = bytearray()
    xref_payload = bytearray()
    for value, refs in words:
        word_payload.extend(WORD.pack(value, first, len(refs)))
        for rva in refs:
            xref_payload.extend(XREF.pack(rva))
        first += len(refs)
    header = HEADER.pack(MAGIC, VERSION, len(words), first)
    return header + bytes(word_payload) + bytes(xref_payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    words = collect(args.report)
    blob = build(words)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d words, %d xrefs, %d bytes" %
          (args.out, len(words), sum(len(refs) for _v, refs in words),
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
