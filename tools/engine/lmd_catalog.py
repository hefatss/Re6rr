r"""Pack gzip/XMD.001 header facts from every shipped .LMD flash file.

    python tools/engine/lmd_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/lmd.r6lmd

Each file is a gzip stream whose inflated bytes start with XMD.001 and contain
three stream offsets. Only the gzip header, ISIZE, XMD version, stream offsets
and derived stream sizes are copied; stream contents are not interpreted.
"""

import argparse
import glob
import gzip
import json
import os
import struct

MAGIC = b"R6LMD\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
FILE = struct.Struct("<10I")
STREAM = struct.Struct("<2I")
FILES = 985
STREAMS_PER_FILE = 3
XMD_HEADER = 0x30
XMD_MAGIC = b"XMD\x00001\x00"


def collect(dump):
    rows = []
    for path in glob.glob(os.path.join(dump, "**", "*.[Ll][Mm][Dd]"),
                          recursive=True):
        with open(path, "rb") as stream:
            raw = stream.read()
        inflated = gzip.decompress(raw)
        if (raw[:2] != b"\x1f\x8b" or raw[2] != 8 or len(raw) < 18 or
                inflated[:8] != XMD_MAGIC):
            raise ValueError("bad gzip/XMD header: %s" % path)
        version, count = struct.unpack_from("<II", inflated, 8)
        offsets = struct.unpack_from("<3I", inflated, 16)
        expected = struct.unpack_from("<I", raw, len(raw) - 4)[0]
        if (version != 1 or count != STREAMS_PER_FILE or
                offsets[0] != XMD_HEADER or
                any(a > b for a, b in zip(offsets, offsets[1:])) or
                offsets[-1] > len(inflated) or expected != len(inflated)):
            raise ValueError("bad XMD layout: %s" % path)
        sizes = [b - a for a, b in
                 zip(offsets, offsets[1:] + (len(inflated),))]
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     len(raw), raw[3], struct.unpack_from("<I", raw, 4)[0],
                     raw[8] | (raw[9] << 8), expected, len(inflated),
                     version, offsets, sizes))
    rows.sort(key=lambda row: row[0])
    if len(rows) != FILES:
        raise ValueError("expected %d .LMD files, found %d" %
                         (FILES, len(rows)))
    return rows


def build(rows):
    strings = bytearray()
    streams = bytearray()
    files = bytearray()
    first = 0
    for (path, compressed, flags, mtime, xfl_os, expected, inflated,
         version, offsets, sizes) in rows:
        raw = path.encode("ascii")
        offset = len(strings)
        strings.extend(raw + b"\0")
        for at, size in zip(offsets, sizes):
            streams.extend(STREAM.pack(at, size))
        files.extend(FILE.pack(offset, len(raw), compressed, flags, mtime,
                               xfl_os, expected, inflated, version, first))
        first += STREAMS_PER_FILE
    header = HEADER.pack(MAGIC, VERSION, len(rows), STREAMS_PER_FILE,
                         len(strings))
    return (header + bytes(files) + bytes(streams) + bytes(strings))


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
            json.dump([{"path": row[0], "compressed": row[1],
                        "inflated": row[6], "offsets": row[8],
                        "sizes": row[9]} for row in rows], stream, indent=2)
    print("%s: %d gzip/XMD.001 LMD headers, %d bytes" %
          (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
