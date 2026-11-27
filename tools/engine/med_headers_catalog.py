r"""Pack the validated 0x100 header of every shipped .MED motion file.

    python tools/engine/med_headers_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/med_headers.r6med

The first 0x100 bytes are zero in all 67 files. The eight u32 words at 0x100
encode frame count, three section sizes, two derived byte counts and the total
file size; the arithmetic is checked here and again by the C reader. No frame
data, animation semantics or bone mapping are inferred.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6MED\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
RECORD = struct.Struct("<11I")
HEADER_OFF = 0x100
WORDS = 8


def collect(dump):
    paths = []
    for path in glob.glob(os.path.join(dump, "**", "*.[Mm][Ee][Dd]"),
                          recursive=True):
        with open(path, "rb") as stream:
            raw = stream.read(HEADER_OFF + WORDS * 4)
        if len(raw) < HEADER_OFF + WORDS * 4 or any(raw[:HEADER_OFF]):
            raise ValueError("bad .MED zero prefix: %s" % path)
        words = struct.unpack_from("<8I", raw, HEADER_OFF)
        frames = words[1]
        size = os.path.getsize(path)
        if (words[0] != 0 or words[2] != 408 or words[3] != 2560 or
                words[4] != frames * 480 or words[5] != 76 or
                words[6] != frames * 60 or words[7] != size):
            raise ValueError("bad .MED header: %s" % path)
        paths.append((os.path.relpath(path, dump).replace("\\", "/"),
                      size, words))
    paths.sort(key=lambda row: row[0])
    return paths


def build(rows):
    strings = bytearray()
    payload = bytearray()
    for path, size, words in rows:
        raw = path.encode("ascii")
        offset = len(strings)
        strings.extend(raw + b"\0")
        payload.extend(RECORD.pack(offset, len(raw), size, *words))
    header = HEADER.pack(MAGIC, VERSION, len(rows), HEADER_OFF, len(strings))
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
            json.dump([{"path": path, "size": size, "header": list(words)}
                       for path, size, words in rows], stream, indent=2)
    print("%s: %d .MED headers, %d bytes" % (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
