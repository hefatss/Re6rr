"""Dump the structure of a gzip-wrapped game asset (NTWD / XMD container).

    python tools/assets/inspect.py <file> [--raw] [--limit N]

Prints the first bytes as hex, as 32-bit words (both endiannesses) and as
0-based offsets so a chunk table can be recognised by hand. With --raw the file
is read as-is; otherwise a gzip member is inflated first.
"""

import argparse
import gzip
import os
import sys


def load(path, raw):
    with open(path, "rb") as f:
        b = f.read()
    if raw or b[:3] != b"\x1f\x8b\x08":
        return b, "raw"
    return gzip.decompress(b), "gzip"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--limit", type=int, default=256)
    ap.add_argument("--out")
    args = ap.parse_args()

    b, how = load(args.path, args.raw)
    lines = ["%s  (%s %d bytes, payload %d)" % (os.path.basename(args.path), how, os.path.getsize(args.path), len(b)), ""]
    lines.append("ascii: " + "".join(chr(c) if 32 <= c < 127 else "." for c in b[:96]))
    lines.append("")
    lines.append("offset   bytes                                            le32 words")
    for off in range(0, min(len(b), args.limit), 16):
        chunk = b[off:off + 16]
        words = " ".join("%08x" % int.from_bytes(chunk[i:i + 4], "little") for i in range(0, len(chunk) - 3, 4))
        lines.append("%08x %-48s %s" % (off, chunk.hex(), words))
    text = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf8") as f:
            f.write(text)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
