r"""Pack the raw 64-byte header prefix of every shipped .NUF font file.

    python tools/engine/nuf_headers_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/nuf_headers.r6nuf

The first four bytes are `NUF\0` in one sample and `NFH\0` in the 21 shipped
fonts. Only the path, file size and first 64 bytes are copied; glyph tables and
font layout are not interpreted.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6NUF\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
RECORD = struct.Struct("<III64s")
PREFIX_SIZE = 64
KNOWN_MAGICS = (b"NUF\0", b"NFH\0")


def collect(dump):
    paths = []
    for path in glob.glob(os.path.join(dump, "**", "*.[Nn][Uu][Ff]"),
                          recursive=True):
        with open(path, "rb") as stream:
            prefix = stream.read(PREFIX_SIZE)
        if len(prefix) < PREFIX_SIZE or prefix[:4] not in KNOWN_MAGICS:
            raise ValueError("unknown .NUF magic: %s" % path)
        paths.append((os.path.relpath(path, dump).replace("\\", "/"),
                      os.path.getsize(path), prefix))
    paths.sort(key=lambda row: row[0])
    if len(paths) != 22:
        raise ValueError("expected 22 .NUF files, found %d" % len(paths))
    return paths


def build(rows):
    strings = bytearray()
    payload = bytearray()
    for path, size, prefix in rows:
        raw = path.encode("ascii")
        offset = len(strings)
        strings.extend(raw + b"\0")
        payload.extend(RECORD.pack(offset, len(raw), size, prefix))
    header = HEADER.pack(MAGIC, VERSION, len(rows), PREFIX_SIZE, len(strings))
    return header + bytes(payload) + bytes(strings)


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
            json.dump([{"path": path, "size": size,
                        "prefix": prefix.hex()} for path, size, prefix in rows],
                      stream, indent=2)
    print("%s: %d NUF/NFH font headers, %d bytes" %
          (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
