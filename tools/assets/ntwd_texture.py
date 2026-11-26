"""Parse NTWD texture streams inside XMD.001 containers.

    python tools/assets/ntwd_texture.py FILE [--raw] [--dump DIR]

Layout below comes from the wmn6r.exe loader (Ghidra FUN_140cae1a0,
FUN_140cbc000, FUN_140cbc0f0, FUN_140cbc190, FUN_140cbc270):

    stream +0x00  "NTWD"
           +0x04  u8  type (1 or 2)
           +0x05  u8  padding
           +0x06  u16 texture count
           +0x10  texture headers, count of them, stride = u16 at header+0xc

    texture header (relative):
      +0x00  u32  type-1 stride, or total size
      +0x08  u32  pixel byte count
      +0x0c  u16  header stride (normally 0x50)
      +0x10  u32  mip-level count byte at +0x11, format byte at +0x13
                  (0 BC1, 1 BC2, 2 BC3, 0x0e G16R16, 0x15 A8R8G8B8)
      +0x14  u16  width
      +0x16  u16  height
      +0x1c  u32  flag bits (bit 9 selects the second table, bit 17 cube)
      +0x20  u32  type-2 pixel offset from header start
      +0x30  face/mip table u32[n], optional
      +0x30  "eXt" chunk (0x10 bytes), shifted by the table and flag bit 9
      +0x40  "GIDX" chunk (0x10 bytes), hash at +8

Pixel blobs live after all texture headers. This module reports offsets and
can dump blobs; decompression of BCn blocks is not attempted.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from xmd_streams import load, parse  # noqa: E402


def parse_stream(d):
    if len(d) < 0x50 or d[:4] != b"NTWD":
        raise ValueError("not an NTWD stream")
    typ, count = d[4], struct.unpack_from("<H", d, 6)[0]
    if typ not in (1, 2):
        raise ValueError("NTWD type %d" % typ)
    textures = []
    at = 0x10
    for i in range(count):
        if at + 0x50 > len(d):
            raise ValueError("texture header %d outside stream" % i)
        block = struct.unpack_from("<III", d, at)
        stride = struct.unpack_from("<H", d, at + 0xc)[0]
        faces = d[at + 0x11]
        fmt = d[at + 0x13]
        width, height = struct.unpack_from("<HH", d, at + 0x14)
        flags = struct.unpack_from("<I", d, at + 0x1c)[0]
        if typ == 1:
            data_off = struct.unpack_from("<H", d, at + 0xc)[0]
        else:
            data_off = struct.unpack_from("<I", d, at + 0x20)[0]
        data_size = block[2]
        # FUN_140cbc190: faces and flag bit 9 move the eXt/GIDX chunks.
        extra = 0 if faces == 1 else (((faces - 1) >> 2) + 1) * 0x10
        gidx = at + 0x40 + extra + (((flags >> 9) & 1) << 4)
        if d[gidx:gidx + 4] != b"GIDX":
            raise ValueError("GIDX missing for texture %d at 0x%x" % (i, gidx))
        hash_ = struct.unpack_from("<I", d, gidx + 8)[0]
        cube = ((flags >> 0x11) & 1) != 0 or ((flags >> 9) & 1) != 0
        textures.append(dict(
            index=i, header=at, stride=stride, hash=hash_,
            width=width, height=height, faces=faces, fmt=fmt,
            flags=flags, cube=cube, data_off=data_off, data_size=data_size,
        ))
        if typ == 1:
            at += block[0]
        else:
            at += stride
    return dict(type=typ, count=count, textures=textures)


def blob(d, t):
    start = t["header"] + t["data_off"]
    return d[start:start + t["data_size"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--stream", type=int, default=-1)
    ap.add_argument("--dump", help="write pixel blobs to this directory")
    args = ap.parse_args()

    b, how = load(args.path, args.raw)
    _, offsets = parse(b)
    print("%s: %s, payload %d, streams %d" % (
        os.path.basename(args.path), how, len(b), len(offsets)))
    for i, start in enumerate(offsets):
        if args.stream >= 0 and i != args.stream:
            continue
        end = offsets[i + 1] if i + 1 < len(offsets) else len(b)
        d = b[start:end]
        info = parse_stream(d)
        print("  stream %d @0x%x size=0x%x type=%d count=%d" % (
            i, start, len(d), info["type"], info["count"]))
        for t in info["textures"]:
            bpp = t["data_size"] * 8 / max(1, t["width"] * t["height"])
            print("    #%d hash=%08x %dx%d faces=%d fmt=%02x flags=%08x "
                  "off=0x%x size=0x%x bpp=%.2f" % (
                      t["index"], t["hash"], t["width"], t["height"],
                      t["faces"], t["fmt"], t["flags"], t["data_off"],
                      t["data_size"], bpp))
            if args.dump:
                os.makedirs(args.dump, exist_ok=True)
                name = "s%d_t%d_%08x.bin" % (i, t["index"], t["hash"])
                with open(os.path.join(args.dump, name), "wb") as f:
                    f.write(blob(d, t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
