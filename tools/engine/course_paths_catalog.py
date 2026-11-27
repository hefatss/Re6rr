"""Pack route metadata and path-bin sizes from the shipped course data.

    python tools/engine/course_paths_catalog.py \
        --dump D:\\Games\\W6W-05 --out build/tmp/course_paths.r6cps

Route rows, their exact `.bin` names and every path file under
`data/course/path` are copied from the dump. Duplicate basenames stay
unresolved: the route table names files, not a disambiguated area path. No
geometry values are copied or interpreted.
"""

import argparse
import glob
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import course_descriptor  # noqa: E402

MAGIC = b"R6CPS\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIII")
ROUTE = struct.Struct("<7I")
REF = struct.Struct("<2I")
FILE = struct.Struct("<4I")
EXPECTED_ROUTES = 33
EXPECTED_REFS = 143
EXPECTED_FILES = 178


def collect(dump):
    routes = []
    for item in course_descriptor.routes(dump):
        if item["area_id"] < -1 or item["loop"] < 0 or \
                item["camera_direction"] < 0 or not item["paths"]:
            raise ValueError("bad route: %s" % item["name"])
        routes.append((item["name"], item["area_id"], item["loop"],
                       item["camera_direction"], list(item["paths"])))
    if len(routes) != EXPECTED_ROUTES:
        raise ValueError("expected %d routes, found %d" %
                         (EXPECTED_ROUTES, len(routes)))
    refs = [name for row in routes for name in row[4]]
    if len(refs) != EXPECTED_REFS:
        raise ValueError("expected %d route path refs, found %d" %
                         (EXPECTED_REFS, len(refs)))

    root = os.path.join(dump, "data", "course", "path")
    files = []
    for path in glob.glob(os.path.join(root, "**", "*.bin"), recursive=True):
        size = os.path.getsize(path)
        if size < 12 or size % 12:
            raise ValueError("bad path bin size: %s" % path)
        files.append((os.path.relpath(path, dump).replace("\\", "/"),
                      size, size // 12))
    files.sort(key=lambda row: row[0])
    if len(files) != EXPECTED_FILES:
        raise ValueError("expected %d path bins, found %d" %
                         (EXPECTED_FILES, len(files)))
    return routes, refs, files


def build(routes, refs, files):
    strings = bytearray()
    strings_base = (HEADER.size + len(routes) * ROUTE.size +
                    len(refs) * REF.size + len(files) * FILE.size)

    def add(value):
        raw = value.encode("ascii")
        offset = strings_base + len(strings)
        strings.extend(raw + b"\0")
        return offset, len(raw)

    route_rows = bytearray()
    ref_rows = bytearray()
    file_rows = bytearray()
    first = 0
    for name, area, loop, direction, paths in routes:
        name_off, name_len = add(name)
        route_rows.extend(ROUTE.pack(name_off, name_len, area & 0xffffffff,
                                     loop, direction, first, len(paths)))
        for path_name in paths:
            off, length = add(path_name)
            ref_rows.extend(REF.pack(off, length))
        first += len(paths)
    for path, size, triples in files:
        off, length = add(path)
        file_rows.extend(FILE.pack(off, length, size, triples))
    header = HEADER.pack(MAGIC, VERSION, len(routes), len(refs), len(files),
                         len(strings))
    return header + bytes(route_rows) + bytes(ref_rows) + bytes(file_rows) + \
        bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    routes, refs, files = collect(args.dump)
    blob = build(routes, refs, files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"routes": routes, "refs": refs, "files": files},
                      stream, indent=2)
    print("%s: %d routes, %d path refs, %d path bins, %d bytes" %
          (args.out, len(routes), len(refs), len(files), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
