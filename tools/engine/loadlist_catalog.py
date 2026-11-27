r"""Pack shipped stage LOADLIST section and stream facts.

    python tools/engine/loadlist_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/loadlist.r6lls

All 76 `LOADLIST_*.lua` files are parsed with course_surface.parse_loadlist().
For every SECTION_ID block the exact `sim:` bin path, wrap facts and NDWD
stream offset/size/name are copied. No stream geometry is decoded and no
surface class is inferred.
"""

import argparse
import glob
import gzip
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import course_surface  # noqa: E402

MAGIC = b"R6LLS\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIII")
FILE = struct.Struct("<4I")
BLOCK = struct.Struct("<8I")
STREAM = struct.Struct("<4I")
EXPECTED_FILES = 76
EXPECTED_BLOCKS = 343
EXPECTED_STREAMS = 17163
NDWD_MAGIC = b"NDWD"
MIN_STREAM = course_surface.SECTION_START


def collect(dump):
    root = os.path.join(dump, "data", "course", "stage")
    paths = sorted(glob.glob(os.path.join(root, "**", "LOADLIST_*.lua"),
                             recursive=True))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d LOADLIST files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    files = []
    blocks = []
    streams = []
    for path in paths:
        parsed = course_surface.parse_loadlist(path)
        first_block = len(blocks)
        for section, binpath, rows in parsed:
            if not os.path.exists(binpath):
                raise ValueError("missing section bin: %s" % binpath)
            raw = open(binpath, "rb").read()
            wrapped = raw[:2] == b"\x1f\x8b"
            inflated = gzip.decompress(raw) if wrapped else raw
            if inflated[:4] != NDWD_MAGIC:
                raise ValueError("bad NDWD magic: %s" % binpath)
            first_stream = len(streams)
            for offset, size, name in rows:
                if offset < 0 or size < MIN_STREAM or \
                        offset + size > len(inflated) or not name.isascii():
                    raise ValueError("bad stream: %s %s" % (binpath, name))
                streams.append((offset, size, name))
            blocks.append((section, os.path.relpath(binpath, dump)
                           .replace("\\", "/"), len(raw), len(inflated),
                           int(wrapped), first_stream, len(rows)))
        files.append((os.path.relpath(path, dump).replace("\\", "/"),
                      first_block, len(blocks) - first_block))
    if len(blocks) != EXPECTED_BLOCKS or len(streams) != EXPECTED_STREAMS:
        raise ValueError("expected %d blocks/%d streams, found %d/%d" %
                         (EXPECTED_BLOCKS, EXPECTED_STREAMS, len(blocks),
                          len(streams)))
    return files, blocks, streams


def build(files, blocks, streams):
    strings = bytearray()
    offsets = {}
    strings_base = (HEADER.size + len(files) * FILE.size +
                    len(blocks) * BLOCK.size + len(streams) * STREAM.size)

    def add(value):
        raw = value.encode("ascii")
        found = offsets.get(raw)
        if found is not None:
            return found, len(raw)
        offset = strings_base + len(strings)
        offsets[raw] = offset
        strings.extend(raw + b"\0")
        return offset, len(raw)

    file_rows = bytearray()
    block_rows = bytearray()
    stream_rows = bytearray()
    for path, first, count in files:
        off, length = add(path)
        file_rows.extend(FILE.pack(off, length, first, count))
    for section, binpath, source, inflated, wrapped, first, count in blocks:
        off, length = add(binpath)
        block_rows.extend(BLOCK.pack(section, off, length, source, inflated,
                                     wrapped, first, count))
    for offset, size, name in streams:
        off, length = add(name)
        stream_rows.extend(STREAM.pack(offset, size, off, length))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(blocks),
                         len(streams), len(strings), 0)
    return header + bytes(file_rows) + bytes(block_rows) + \
        bytes(stream_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, blocks, streams = collect(args.dump)
    blob = build(files, blocks, streams)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"files": files, "blocks": blocks, "streams": streams},
                      stream, indent=2)
    print("%s: %d LOADLIST files, %d blocks, %d streams, %d bytes" %
          (args.out, len(files), len(blocks), len(streams), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
