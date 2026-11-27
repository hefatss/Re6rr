r"""Pack raw .MTMP stage-effect model tables.

    python tools/engine/mtmp_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/mtmp.r6mtmp

Every non-empty line is either `SCALE:<value>` or an `OBJECT:` record with three
tab-separated fields. The value, object id, parent id and flag list are copied
verbatim; transform semantics are not inferred.
"""

import argparse
import glob
import json
import os
import struct

MAGIC = b"R6MTMP\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
FILE = struct.Struct("<6I")
OBJECT = struct.Struct("<2I")
EXPECTED_FILES = 34


def collect(dump):
    files = []
    for path in glob.glob(os.path.join(dump, "**", "*.mtmp"), recursive=True):
        with open(path, "rb") as stream:
            raw = stream.read().decode("ascii")
        lines = [line for line in raw.splitlines() if line]
        if not lines or not lines[0].startswith("SCALE:") or not lines[0][6:]:
            raise ValueError("bad SCALE line: %s" % path)
        objects = []
        for line in lines[1:]:
            if not line.startswith("OBJECT:"):
                raise ValueError("bad OBJECT line: %s: %s" % (path, line))
            value = line[len("OBJECT:"):]
            if len(value.split("\t")) != 3 or any(not x for x in value.split("\t")):
                raise ValueError("bad OBJECT fields: %s: %s" % (path, line))
            objects.append(value)
        files.append((os.path.relpath(path, dump).replace("\\", "/"),
                      os.path.getsize(path), lines[0][6:], objects))
    files.sort(key=lambda row: row[0])
    if len(files) != EXPECTED_FILES:
        raise ValueError("expected %d .mtmp files, found %d" %
                         (EXPECTED_FILES, len(files)))
    return files


def build(files):
    strings = bytearray()
    objects = bytearray()
    rows = bytearray()

    def add(value):
        offset = len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    first = 0
    for path, size, scale, values in files:
        path_off = add(path)
        scale_off = add(scale)
        for value in values:
            off = add(value)
            objects.extend(OBJECT.pack(off, len(value)))
        rows.extend(FILE.pack(path_off, len(path), size, scale_off,
                              first, len(values)))
        first += len(values)
    header = HEADER.pack(MAGIC, VERSION, len(files), first, len(strings))
    return header + bytes(rows) + bytes(objects) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files = collect(args.dump)
    blob = build(files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump([{"path": path, "size": size, "scale": scale,
                        "objects": objects}
                       for path, size, scale, objects in files], stream,
                      indent=2)
    print("%s: %d .MTMP files, %d object rows, %d bytes" %
          (args.out, len(files), sum(len(row[3]) for row in files), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
