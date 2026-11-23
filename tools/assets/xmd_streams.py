"""Walk an XMD.001 stream table and cluster the streams by their leading bytes.

    python tools/assets/xmd_streams.py FILE [--detail] [--limit N]

XMD.001 layout (all little endian), observed on this dump:

    +0x00  8 bytes  "XMD\\x00001\\x00"
    +0x08  u32      version (3)
    +0x0c  u32      stream count
    +0x10  u32[n]   absolute offsets into the inflated payload

The gap between the offset table and the first stream holds other tables; this
tool only looks at the streams themselves. With no --detail it prints one line
per distinct leading 4-byte tag, which is enough to see where geometry,
materials and animation streams begin.
"""

import argparse
import gzip
import os
import struct
import sys


def load(path, raw):
    with open(path, "rb") as f:
        b = f.read()
    if raw or b[:3] != b"\x1f\x8b\x08":
        return b, "raw"
    return gzip.decompress(b), "gzip"


def parse(b):
    if b[:7] != b"XMD\x00001":
        raise ValueError("not an XMD.001 container: %r" % b[:8])
    version, count = struct.unpack_from("<II", b, 8)
    off = 16 + 4 * count
    if off > len(b):
        raise ValueError("truncated offset table")
    offsets = list(struct.unpack_from("<%dI" % count, b, 16))
    if any(offsets[i] >= offsets[i + 1] for i in range(count - 1)):
        raise ValueError("offset table not monotonic")
    if offsets and offsets[-1] >= len(b):
        raise ValueError("last offset outside payload")
    return version, offsets


def ascii_of(data):
    return "".join(chr(c) if 32 <= c < 127 else "." for c in data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--limit", type=int, default=8, help="samples per cluster")
    args = ap.parse_args()

    b, how = load(args.path, args.raw)
    try:
        version, offsets = parse(b)
    except ValueError as exc:
        print("%s: %s" % (args.path, exc))
        return 1

    streams = []
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < len(offsets) else len(b)
        head = b[start:start + 32]
        tag = head[:4]
        streams.append((i, start, end - start, tag, head))

    clusters = {}
    for s in streams:
        clusters.setdefault(s[3], []).append(s)

    print("%s  (%s, payload %d bytes)" % (os.path.basename(args.path), how, len(b)))
    print("XMD.001 version=%d streams=%d distinct leading tags=%d"
          % (version, len(streams), len(clusters)))
    print()
    print("tag        count  min-size  max-size  first stream")
    for tag, group in sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        sizes = [g[2] for g in group]
        first = group[0]
        print("%-10s %5d  %8d  %8d  #%d @0x%x: %s"
              % (tag.hex(), len(group), min(sizes), max(sizes),
                 first[0], first[1], ascii_of(first[4][:20])))

    if args.detail:
        print()
        print("index  offset      size      tag        first 32 bytes")
        for i, start, size, tag, head in streams:
            print("%5d  0x%08x  %8d  %-10s %s"
                  % (i, start, size, tag.hex(), head.hex()))

    if args.limit:
        print()
        print("samples (up to %d per tag)" % args.limit)
        for tag, group in sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print("  tag %s:" % tag.hex())
            for i, start, size, _, head in group[:args.limit]:
                print("    #%-3d @0x%08x %7d bytes  %s  %s"
                      % (i, start, size, head[:16].hex(), ascii_of(head[:16])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
