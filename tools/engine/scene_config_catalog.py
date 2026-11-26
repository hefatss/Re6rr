"""Pack the shipped Environment.Lua name tables into a C-readable blob.

    python tools/engine/scene_config_catalog.py --dump D:\\Games\\W6W-05 \
        --out build\\tmp\\scene_config.r6scn

Rows come from `wmn6r.exe` VAs recovered in tools/engine/scene_config.py:
254 car names, 149 stage names and 5 day names. No game data is committed;
the output is derived data for the freestanding core.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
sys.path.insert(0, HERE)

import scene_config  # noqa: E402
from pe_report import PE  # noqa: E402

MAGIC = b"R6SCN\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIIIII")


def collect(dump):
    return scene_config.name_tables(PE(os.path.join(dump, "wmn6r.exe")))


def build(tables):
    items = [tables["cars"], tables["stages"], tables["days"]]
    total = sum(len(table) for table in items)
    strings_off = HEADER.size + total * 4
    strings = bytearray()
    offsets = []
    for table in items:
        row = []
        for name in table:
            encoded = name.encode("utf8") + b"\0"
            row.append(strings_off + len(strings))
            strings.extend(encoded)
        offsets.append(row)
    header = HEADER.pack(MAGIC, VERSION, *(len(table) for table in items),
                         strings_off, strings_off, strings_off, len(strings))
    return header + b"".join(struct.pack("<%dI" % len(row), *row)
                             for row in offsets) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    tables = collect(args.dump)
    blob = build(tables)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d car, %d stage, %d day names, %d bytes" %
          (args.out, len(tables["cars"]), len(tables["stages"]),
           len(tables["days"]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
