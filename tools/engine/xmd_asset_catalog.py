r"""Pack XMD.001 header facts from every shipped .TEX and .MDL asset.

    python tools/engine/xmd_asset_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/xmd_assets.r6xas

Each file is gzip-wrapped except eight raw .TEX files. The inflated bytes start
with XMD.001 version 3 and a variable-length offset table. Only the path, wrap
facts, ISIZE, XMD version and stream offsets/sizes are copied; stream contents
are not interpreted.
"""

import argparse
import glob
import gzip
import json
import os
import struct

MAGIC = b"R6XAS\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
FILE = struct.Struct("<13I")
STREAM = struct.Struct("<2I")
XMD_MAGIC = b"XMD\x00001\x00"
XMD_VERSION = 3
EXPECTED_FILES = 1860
EXTENSIONS = {"tex": 0, "mdl": 1}


def collect(dump):
    rows = []
    for path in glob.glob(os.path.join(dump, "**", "*.[Tt][Ee][Xx]"),
                          recursive=True) + glob.glob(
            os.path.join(dump, "**", "*.[Mm][Dd][Ll]"), recursive=True):
        with open(path, "rb") as stream:
            raw = stream.read()
        wrapped = raw[:2] == b"\x1f\x8b"
        if wrapped:
            inflated = gzip.decompress(raw)
            if len(raw) < 18 or raw[2] != 8:
                raise ValueError("bad gzip header: %s" % path)
            flags = raw[3]
            mtime = struct.unpack_from("<I", raw, 4)[0]
            xfl_os = raw[8] | (raw[9] << 8)
            expected = struct.unpack_from("<I", raw, len(raw) - 4)[0]
            if expected != len(inflated):
                raise ValueError("bad gzip ISIZE: %s" % path)
        else:
            inflated = raw
            flags = mtime = xfl_os = expected = 0
        if inflated[:8] != XMD_MAGIC:
            raise ValueError("bad XMD magic: %s" % path)
        version, count = struct.unpack_from("<II", inflated, 8)
        if version != XMD_VERSION or count < 1 or 16 + 4 * count > len(inflated):
            raise ValueError("bad XMD header: %s" % path)
        offsets = struct.unpack_from("<%dI" % count, inflated, 16)
        if (offsets[0] < 16 + 4 * count or
                any(a > b for a, b in zip(offsets, offsets[1:])) or
                offsets[-1] > len(inflated)):
            raise ValueError("bad XMD stream table: %s" % path)
        sizes = [b - a for a, b in
                 zip(offsets, offsets[1:] + (len(inflated),))]
        extension = os.path.splitext(path)[1][1:].lower()
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     EXTENSIONS[extension], int(wrapped), len(raw),
                     len(inflated), flags, mtime, xfl_os, expected,
                     version, offsets, sizes))
    rows.sort(key=lambda row: row[0])
    if len(rows) != EXPECTED_FILES:
        raise ValueError("expected %d .TEX/.MDL files, found %d" %
                         (EXPECTED_FILES, len(rows)))
    return rows


def build(rows):
    strings = bytearray()
    streams = bytearray()
    files = bytearray()
    first = 0
    strings_base = (HEADER.size + len(rows) * FILE.size +
                    sum(len(row[10]) for row in rows) * STREAM.size)
    for (path, ext, wrap, source, inflated, flags, mtime, xfl_os,
         expected, version, offsets, sizes) in rows:
        raw = path.encode("ascii")
        path_off = strings_base + len(strings)
        strings.extend(raw + b"\0")
        for offset, size in zip(offsets, sizes):
            streams.extend(STREAM.pack(offset, size))
        files.extend(FILE.pack(path_off, len(raw), ext, wrap, source,
                               inflated, flags, mtime, xfl_os, expected,
                               version, first, len(offsets)))
        first += len(offsets)
    header = HEADER.pack(MAGIC, VERSION, len(rows), first, len(strings))
    return header + bytes(files) + bytes(streams) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    rows = collect(args.dump)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump([{"path": row[0], "ext": row[1], "wrapped": row[2],
                        "source_size": row[3], "inflated_size": row[4],
                        "offsets": row[10], "sizes": row[11]} for row in rows],
                      stream, indent=2)
    print("%s: %d XMD.001 asset headers, %d streams, %d bytes" %
          (args.out, len(rows), sum(len(row[10]) for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
