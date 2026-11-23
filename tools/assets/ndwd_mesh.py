"""Reconstruct one NDWD/NTWD mesh as a Wavefront OBJ.

    python tools/assets/ndwd_mesh.py FILE [--stream N] [--out FILE]

The layout below was measured from this dump (PLC_BNR34.mdl, stream 0/1):

    XMD stream at offset S
    +0x00  "NDWD" or "NTWD"
    +0x04  u32 id/hash
    +0x08  u32 version (2)
    +0x0c  u32 kind (1/2)
    +0x10  u32 size[3]     section byte sizes
    +0x14  u32 size[1]
    +0x18  u32 size[2]
    +0x50  section 0: material / bone records
           section 1: u16 indices, 0xffff ends a triangle strip
           section 2: 28-byte vertices:
                      f32 x, y, z, f32 param, u32 0xffffffff, f32 u, f32 v

Nothing here is authoritative: it is a working decode checked against the byte
patterns, not a format specification.
"""

import argparse
import gzip
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from xmd_streams import load, parse  # noqa: E402


def sections(b, start, end):
    if end - start < 0x50:
        raise ValueError("stream too small for NDWD header")
    d = b[start:start + 0x50]
    if d[:4] not in (b"NDWD", b"NTWD"):
        raise ValueError("not an NDWD/NTWD stream: %r" % d[:4])
    sizes = struct.unpack_from("<III", d, 0x10)
    off = 0x50
    out = []
    for size in sizes:
        if off + size > end - start:
            raise ValueError("section outside stream")
        out.append(b[start + off:start + off + size])
        off += size
    version, kind = struct.unpack_from("<HH", d, 8)
    return (version, kind), sizes, out


def read_mesh(sec1, sec2):
    vertex_capacity = len(sec2) // 28
    indices = struct.unpack_from("<%dH" % (len(sec1) // 2), sec1, 0)
    strips = []
    cur = []
    trailing = 0
    for i in indices:
        if i == 0xFFFF:
            if len(cur) >= 3:
                strips.append(cur)
            cur = []
        elif i >= vertex_capacity:
            # The tail of section 1 is not index data; stop there.
            trailing += 1
            if cur:
                cur = []
        else:
            cur.append(i)
    if len(cur) >= 3:
        strips.append(cur)

    # The 0xffffffff word is the bone-id field of a 28-byte vertex. Most of
    # section 2 is a run of such vertices, but some offsets switch to another
    # layout, so locate the runs instead of assuming one stride over the whole
    # section.
    words = struct.unpack_from("<%dI" % (len(sec2) // 4), sec2, 0)
    ff = [i for i, w in enumerate(words) if w == 0xFFFFFFFF]
    verts = {}
    used = set()
    for p in ff:
        first = p - 4
        if first < 0 or first % 7 or p + 3 >= len(words):
            continue
        if any(w in used for w in range(first, p + 3)):
            continue
        x, y, z, param, flag, u, v = struct.unpack_from("<ffffIff", sec2, first * 4)
        verts[first // 7] = (x, y, z, param, u, v)
        used.update(range(first, p + 3))
    pad = len(words) - len(used)
    return verts, strips, pad, trailing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--stream", type=int, default=0)
    ap.add_argument("--out", help="write OBJ here (default: stdout)")
    args = ap.parse_args()

    b, how = load(args.path, args.raw)
    _, offsets = parse(b)
    if not 0 <= args.stream < len(offsets):
        raise SystemExit("stream %d out of range (0..%d)" % (args.stream, len(offsets) - 1))
    start = offsets[args.stream]
    end = offsets[args.stream + 1] if args.stream + 1 < len(offsets) else len(b)

    (version, kind), sizes, secs = sections(b, start, end)
    verts, strips, vtx_pad, sep_count = read_mesh(secs[1], secs[2])

    print("%s: %s, stream %d @0x%x, version=%d kind=%d" % (
        os.path.basename(args.path), how, args.stream, start, version, kind))
    print("  sections: %s" % ["0x%x" % s for s in sizes])
    if os.environ.get("NDWD_DEBUG"):
        print("  debug sec1 len=%d head=%s" % (
            len(secs[1]), list(struct.unpack_from("<16H", secs[1], 0))))
    max_index = max((max(s) for s in strips), default=-1)
    print("  vertices decoded: %d, %d words unused" % (len(verts), vtx_pad))
    print("  strips: %d, %d trailing non-index words, max index %d" % (
        len(strips), sep_count, max_index))
    if max_index >= len(verts) and max_index not in verts:
        print("  warning: index buffer reaches %d, only %d vertices decoded" % (
            max_index, len(verts)))

    lines = ["# reconstructed from %s stream %d" % (args.path, args.stream)]
    dense = [verts.get(i, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)) for i in range(max_index + 1)]
    lines += ["v %.8g %.8g %.8g" % v[:3] for v in dense]
    lines += ["vt %.8g %.8g" % v[4:] for v in dense]
    for strip in strips:
        for i in range(len(strip) - 2):
            a, b_, c = strip[i:i + 3]
            # Keep strip winding; OBJ indices are 1-based.
            lines.append("f %d/%d %d/%d %d/%d" % (
                a + 1, a + 1, b_ + 1, b_ + 1, c + 1, c + 1))
    text = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w", encoding="ascii") as f:
            f.write(text)
        print("  wrote OBJ: %s" % args.out)
    else:
        print("  OBJ would be %d lines (use --out)" % len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
