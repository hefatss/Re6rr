"""Dump NDWD header, mesh groups and material records.

    python tools/assets/ndwd_records.py FILE [--stream N]

The structure comes from the wmn6r.exe loader decompiled in Ghidra
(FUN_140ca78b0, FUN_140ca7b00, FUN_140ca7c10, FUN_140ca7ed0):

    +0x00  "NDWD"
    +0x04  u32 id
    +0x08  u16 version = 2
    +0x0a  u16 group count
    +0x10  u32 section sizes[4] (sections start at 0x50)
    +0x30  u32 name_off, ..., u16 sub_count, u32 sub_start   (0x30 each)

Each subrecord at sub_start + j*0x30 holds four u32 texture hashes at +0x10.
The material chain starts at sub+0x20 + u16(sub+0xa)*0x18 and walks u32-sized
records. Section 2 holds 28-byte vertex runs, but more than one vertex layout
occurs in it, so this tool reports runs rather than decoding the mesh.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from xmd_streams import load, parse  # noqa: E402


def u16(d, at):
    return struct.unpack_from("<H", d, at)[0]


def u32(d, at):
    return struct.unpack_from("<I", d, at)[0]


def stream_info(d):
    if d[:4] != b"NDWD":
        raise ValueError("not an NDWD stream: %r" % d[:4])
    sizes = struct.unpack_from("<4I", d, 0x10)
    sec0_end = 0x50 + sizes[0]
    if sec0_end > len(d):
        raise ValueError("section 0 outside stream")
    groups = []
    for gi in range(u16(d, 0xa)):
        g = 0x30 + gi * 0x30
        nsub = u16(d, g + 0x2a)
        sub_start = u32(d, g + 0x2c)
        subs = []
        for sj in range(nsub):
            sub = sub_start + sj * 0x30
            if sub + 0x30 > sec0_end:
                raise ValueError("subrecord %d outside section 0" % sj)
            hashes = struct.unpack_from("<4I", d, sub + 0x10)
            extra = u16(d, sub + 0xa)
            chain = sub + 0x20 + extra * 0x18
            records = []
            while chain + 0x10 <= len(d):
                size = u32(d, chain)
                if size == 0:
                    break
                flag = d[chain + 0xb]
                records.append((chain, size, u32(d, chain + 4), flag))
                if flag == 0:
                    break
                chain += size
            subs.append(dict(index=sj, offset=sub, hashes=hashes,
                             extra=extra, records=records))
        groups.append(dict(index=gi, offset=g, name_off=u32(d, g + 0x20),
                           nsub=nsub, sub_start=sub_start, subs=subs))
    return dict(id=u32(d, 4), version=u16(d, 8), group_count=u16(d, 0xa),
                sizes=sizes, groups=groups)


def vertex_runs(sec2):
    words = struct.unpack_from("<%dI" % (len(sec2) // 4), sec2, 0)
    ff = [i for i, w in enumerate(words) if w == 0xFFFFFFFF]
    runs = []
    if ff:
        start = prev = ff[0]
        for x in ff[1:]:
            if x - prev != 7:
                runs.append((start * 4, prev * 4, (prev - start) // 7 + 1))
                start = x
            prev = x
        runs.append((start * 4, prev * 4, (prev - start) // 7 + 1))
    return runs, len(ff)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--stream", type=int, default=0)
    args = ap.parse_args()

    b, how = load(args.path, args.raw)
    _, offsets = parse(b)
    if not 0 <= args.stream < len(offsets):
        raise SystemExit("stream %d out of range" % args.stream)
    start = offsets[args.stream]
    end = offsets[args.stream + 1] if args.stream + 1 < len(offsets) else len(b)
    d = b[start:end]
    info = stream_info(d)

    print("%s: %s, stream %d @0x%x" % (
        os.path.basename(args.path), how, args.stream, start))
    print("  id=%08x version=%d groups=%d sizes=%s" % (
        info["id"], info["version"], info["group_count"],
        ["0x%x" % x for x in info["sizes"]]))
    for g in info["groups"]:
        print("  group%d @0x%x name_off=%d subs=%d start=0x%x" % (
            g["index"], g["offset"], g["name_off"], g["nsub"], g["sub_start"]))
        for sub in g["subs"]:
            print("    sub%d @0x%x hashes=%s" % (
                sub["index"], sub["offset"],
                [hex(x) for x in sub["hashes"]]))
            for at, size, off, flag in sub["records"]:
                print("      record @0x%x size=0x%x off=%d flag=%02x" % (
                    at, size, off, flag))
    off = 0x50
    for i, size in enumerate(info["sizes"][:3]):
        print("  section%d @0x%x size=0x%x" % (i, off, size))
        off += size
    sec2 = d[0x50 + info["sizes"][0] + info["sizes"][1]:
             0x50 + sum(info["sizes"][:3])]
    runs, count = vertex_runs(sec2)
    print("  section2: %d 0xffffffff markers, %d runs of 28-byte vertices" % (
        count, len(runs)))
    for at, size, n in runs:
        print("    @0x%x..0x%x %d vertices" % (at, size, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
