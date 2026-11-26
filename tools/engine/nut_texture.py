"""Inventory and decode shipped `.nut` texture containers.

    python tools/engine/nut_texture.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/nut_texture.json
    python tools/engine/nut_texture.py --decode FILE --entry 0 --png out.png

Containers are either gzip-wrapped or raw NTWD/NTLX. Both start with a 0x10
prefix; the descriptor size at +0x1c is 0x50..0x80. Format bytes come from the
wmn6r.exe NTWD loader: 0 = BC1, 1 = BC2, 2 = BC3, 0x15 = A8R8G8B8 and
0x0e = G16R16 (D3DFMT numeric value 14). Byte +0x11 is the mip-level count for
the payload, not a cube-face count. Payload layout is validated by
`test_nut_texture.py`; RGBA8 decode here covers four formats, not G16R16.

"""

import argparse
import gzip
import json
import os
import struct
import zlib

NTWD = b"NTWD"
NTLX = b"NTLX"
GZIP = b"\x1f\x8b"
PREFIX_SIZE = 0x10
GIDX_OFFSET = 0x30
FORMAT_NAMES = {0: "BC1", 1: "BC2", 2: "BC3", 0x0e: "G16R16",
                0x15: "A8R8G8B8"}
BLOCK_BYTES = {0: 8, 1: 16, 2: 16}


def read_nut(path):
    """Return inflated container bytes."""
    with open(path, "rb") as stream:
        raw = stream.read()
    if raw[:2] == GZIP:
        raw = gzip.decompress(raw)
    if raw[:4] not in (NTWD, NTLX):
        raise ValueError("unknown .nut container: %s" % path)
    return raw


def parse_nut(path):
    """Return NTWD/NTLX header layout metadata for one shipped file."""
    raw = read_nut(path)
    compressed = open(path, "rb").read(2) == GZIP
    result = {"path": os.path.relpath(path).replace("\\", "/"),
              "compressed": compressed, "size": len(raw)}
    version, entries = struct.unpack_from("<HH", raw, 4)
    total, payload_size, descriptor_size = struct.unpack_from("<QII", raw,
                                                               0x10)
    packed0, packed1 = struct.unpack_from("<II", raw, 0x20)
    gidx = struct.unpack_from("<Q", raw, GIDX_OFFSET)[0]
    payload_offset = PREFIX_SIZE + entries * descriptor_size
    width, height = packed1 & 0xffff, packed1 >> 16
    pixels = width * height
    bpp = payload_size // pixels if pixels and payload_size % pixels == 0 \
        else None
    result.update({
        "container": "NTWD" if raw[:4] == NTWD else "NTLX",
        "version": version, "entries": entries,
        "total": total, "payload_size": payload_size,
        "descriptor_size": descriptor_size,
        "packed0": (packed0 & 0xffff, packed0 >> 16),
        "dimensions": (width, height),
        "gidx": gidx, "payload_offset": payload_offset,
        "bytes_per_pixel": bpp,
        "exact": len(raw) == payload_offset + entries * payload_size,
    })
    return result


def parse_entries(raw):
    """Return per-texture format/mip layout for an inflated NTWD/NTLX blob."""
    kind = raw[:4]
    if kind not in (NTWD, NTLX):
        raise ValueError("not an NTWD/NTLX container")
    typ = raw[4]
    if typ not in (1, 2):
        raise ValueError("unsupported .nut type %d" % typ)
    count = struct.unpack_from("<H", raw, 6)[0]
    pos = 0x10
    result = []
    for index in range(count):
        if pos + 0x50 > len(raw):
            break
        total = struct.unpack_from("<Q", raw, pos)[0]
        data_size = struct.unpack_from("<I", raw, pos + 0x08)[0]
        stride = struct.unpack_from("<H", raw, pos + 0x0c)[0]
        levels = raw[pos + 0x11]
        fmt = raw[pos + 0x13]
        width, height = struct.unpack_from("<HH", raw, pos + 0x14)
        flags = struct.unpack_from("<I", raw, pos + 0x1c)[0]
        data_offset = stride if typ == 1 else struct.unpack_from(
            "<I", raw, pos + 0x20)[0]
        start = pos + data_offset
        cube = bool((flags >> 9) & 1) or bool((flags >> 0x11) & 1)
        result.append({
            "index": index, "container": kind.decode(),
            "type": typ, "format": fmt, "format_name": FORMAT_NAMES.get(fmt),
            "levels": levels, "cube": cube, "flags": flags,
            "width": width, "height": height,
            "data_offset": data_offset, "data_start": start,
            "data_size": data_size, "header": pos, "stride": stride,
        })
        pos += total if typ == 1 else stride
    return result


def level_size(fmt, width, height):
    """Size of one mip level, rounded to the 16-byte container alignment."""
    if fmt in (0x0e, 0x15):
        size = width * height * 4
    elif fmt in BLOCK_BYTES:
        size = ((width + 3) // 4) * ((height + 3) // 4) * BLOCK_BYTES[fmt]
    else:
        raise ValueError("unknown .nut pixel format %d" % fmt)
    return (size + 15) // 16 * 16


def expected_size(entry):
    """Expected payload size for one texture, including mips and cube faces."""
    width, height = entry["width"], entry["height"]
    size = 0
    for level in range(entry["levels"]):
        w = max(1, width >> level)
        h = max(1, height >> level)
        size += level_size(entry["format"], w, h)
    return size * (6 if entry["cube"] else 1)


def available_levels(entry):
    """Number of mip levels actually present in the declared payload."""
    face_size = entry["data_size"] // (6 if entry["cube"] else 1)
    total = 0
    for level in range(entry["levels"]):
        size = level_size(entry["format"],
                          max(1, entry["width"] >> level),
                          max(1, entry["height"] >> level))
        if total + size > face_size:
            return level
        total += size
    return entry["levels"]


def mip_layout(entry, face=0):
    """Yield (offset, width, height, size) for each level of one cube face."""
    face_size = expected_size(entry) // (6 if entry["cube"] else 1)
    offset = entry["data_start"] + face * face_size
    for level in range(available_levels(entry)):
        width = max(1, entry["width"] >> level)
        height = max(1, entry["height"] >> level)
        size = level_size(entry["format"], width, height)
        yield offset, width, height, size
        offset += size


def _rgb565(value):
    return (value >> 11 & 0x1f) * 255 // 31, \
           (value >> 5 & 0x3f) * 255 // 63, \
           (value & 0x1f) * 255 // 31


def _bc1_colors(block):
    c0, c1 = struct.unpack_from("<HH", block, 0)
    a, b = _rgb565(c0), _rgb565(c1)
    if c0 > c1:
        colors = (a, b,
                  tuple((2 * a[i] + b[i]) // 3 for i in range(3)),
                  tuple((a[i] + 2 * b[i]) // 3 for i in range(3)))
    else:
        colors = (a, b, tuple((a[i] + b[i]) // 2 for i in range(3)), (0, 0, 0))
    return colors


def _bc3_alpha(a0, a1, index):
    if a0 > a1:
        return ((7 - index) * a0 + index * a1 + 3) // 7
    if index < 2:
        return a0 if index == 0 else a1
    if index == 6:
        return 0
    if index == 7:
        return 255
    return ((6 - index) * a0 + (index - 1) * a1 + 2) // 5


def _decode_block(fmt, block):
    alphas = None
    if fmt == 1:
        alphas = []
        for byte in block[:8]:
            alphas.extend(((byte & 0xf) * 17, (byte >> 4) * 17))
        block = block[8:]
    elif fmt == 2:
        a0, a1 = block[0], block[1]
        bits = int.from_bytes(block[2:8], "little")
        alphas = [_bc3_alpha(a0, a1, bits >> (3 * i) & 7) for i in range(16)]
        block = block[8:]
    colors = _bc1_colors(block)
    indices = struct.unpack_from("<I", block, 4)[0]
    out = []
    for i in range(16):
        r, g, b = colors[indices >> (2 * i) & 3]
        out.append((r, g, b, 255 if alphas is None else alphas[i]))
    return out


def _decode_bc(fmt, raw, offset, width, height, size):
    payload = raw[offset:offset + size]
    out = bytearray(width * height * 4)
    blocks_x = (width + 3) // 4
    block_bytes = BLOCK_BYTES[fmt]
    for by in range((height + 3) // 4):
        for bx in range(blocks_x):
            at = (by * blocks_x + bx) * block_bytes
            pixels = _decode_block(fmt, payload[at:at + block_bytes])
            for y in range(4):
                py = by * 4 + y
                if py >= height:
                    continue
                for x in range(4):
                    px = bx * 4 + x
                    if px >= width:
                        continue
                    rgba = pixels[y * 4 + x]
                    dst = (py * width + px) * 4
                    out[dst:dst + 4] = bytes(rgba)
    return bytes(out)


def decode_entry(raw, entry, level=0, face=0):
    """Decode one mip level of one cube face to RGBA8 bytes."""
    fmt = entry["format"]
    layout = list(mip_layout(entry, face))
    if not 0 <= level < len(layout):
        raise ValueError("mip level %d outside %d levels" % (level,
                                                             len(layout)))
    offset, width, height, size = layout[level]
    if fmt == 0x0e:
        raise ValueError("G16R16 decode not implemented")
    if fmt == 0x15:
        payload = raw[offset:offset + size]
        out = bytearray(width * height * 4)
        for i in range(width * height):
            b, g, r, a = payload[i * 4:i * 4 + 4]
            out[i * 4:i * 4 + 4] = bytes((r, g, b, a))
        return bytes(out)
    return _decode_bc(fmt, raw, offset, width, height, size)


def write_png(path, width, height, rgba):
    """Write RGBA8 bytes as a PNG without third-party dependencies."""
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + \
            struct.pack(">I", zlib.crc32(body) & 0xffffffff)

    rows = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4]
                    for y in range(height))
    with open(path, "wb") as stream:
        stream.write(b"\x89PNG\r\n\x1a\n")
        stream.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height,
                                                8, 6, 0, 0, 0)))
        stream.write(chunk(b"IDAT", zlib.compress(rows, 9)))
        stream.write(chunk(b"IEND", b""))


def nut_payload(path):
    """Return the first entry's payload bytes from an NTWD/NTLX container."""
    raw = read_nut(path)
    entries = parse_entries(raw)
    if not entries:
        return b""
    entry = entries[0]
    return raw[entry["data_start"]:entry["data_start"] + entry["data_size"]]


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
    parser.add_argument("--decode", help="decode one .nut entry")
    parser.add_argument("--entry", type=int, default=0)
    parser.add_argument("--level", type=int, default=0)
    parser.add_argument("--face", type=int, default=0)
    parser.add_argument("--png", help="write decoded RGBA to this PNG path")
    args = parser.parse_args()
    if args.decode:
        raw = read_nut(args.decode)
        entries = parse_entries(raw)
        if not 0 <= args.entry < len(entries):
            print("entry %d outside %d textures" % (args.entry, len(entries)))
            return 1
        entry = entries[args.entry]
        rgba = decode_entry(raw, entry, args.level, args.face)
        print("%s #%d %s %dx%d level=%d face=%d -> %d RGBA bytes" % (
            args.decode, args.entry, entry["format_name"], entry["width"],
            entry["height"], args.level, args.face, len(rgba)))
        if args.png:
            layout = list(mip_layout(entry, args.face))
            _, width, height, _ = layout[args.level]
            write_png(args.png, width, height, rgba)
        return 0
    rows = collect(args.dump)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf8") as stream:
            json.dump({"files": rows}, stream, indent=2)
    ntwd = [row for row in rows if row["container"] == "NTWD"]
    print("%d .nut files: %d NTWD (%d gzip), %d NTLX, %d exact layouts" %
          (len(rows), len(ntwd), sum(row["compressed"] for row in ntwd),
           len(rows) - len(ntwd), sum(row.get("exact", False) for row in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
