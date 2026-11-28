r"""Pack shipped NavimapParam.lua structural facts.

    python tools/engine/navimap_param_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/navimap_param.r6nvm

Path, copied ASCII global names and integer literals are packed. Shift-JIS
comment text and navimap behavior are not parsed.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6NVM\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s10I")
SCALAR = struct.Struct("<5I")
SPAN = struct.Struct("<2I")
SOURCE = "data/course/parameter/navimap/NavimapParam.lua"
SOURCE_BYTES = 1137
SOURCE_LINES = 32
SCALARS = 4
TABLE_VALUES = 11
SCALAR_ROW = re.compile(r"^(--)?(NAVIMAP_[A-Z_]+)\t\t= (\d+)\t\t-- ")
TABLE_ROW = re.compile(r"^\t([012]),\t\t-- ")


def collect(dump):
    path = os.path.join(dump, *SOURCE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != SOURCE_BYTES or raw.count(b"\r\n") != SOURCE_LINES:
        raise ValueError("unexpected NavimapParam.lua shape")
    lines = raw.decode("cp932", errors="replace").splitlines()
    if len(lines) != SOURCE_LINES:
        raise ValueError("unexpected NavimapParam.lua line count")
    scalars = []
    for line in lines:
        match = SCALAR_ROW.match(line)
        if match:
            scalars.append((match.group(2), match.group(3),
                            0 if match.group(1) else 1))
    if len(scalars) != SCALARS or \
            [row[0] for row in scalars] != ["NAVIMAP_FIELD_OF_VIEW",
                                            "NAVIMAP_CENTER_TO_CAR",
                                            "NAVIMAP_FIELD_OF_VIEW",
                                            "NAVIMAP_CENTER_TO_CAR"] or \
            [row[2] for row in scalars] != [1, 1, 0, 0]:
        raise ValueError("unexpected NavimapParam.lua scalars")
    if lines[18] != "NAVIMAP_USE = {" or lines[30] != "}":
        raise ValueError("unexpected NavimapParam.lua table frame")
    values = []
    for line in lines[19:30]:
        match = TABLE_ROW.match(line)
        if not match:
            raise ValueError("unexpected NavimapParam.lua table row")
        values.append(match.group(1))
    if len(values) != TABLE_VALUES:
        raise ValueError("unexpected NavimapParam.lua table total")
    return scalars, values


def build(scalars, values):
    strings_base = HEADER.size + len(scalars) * SCALAR.size + \
        len(values) * SPAN.size
    strings = bytearray()
    offsets = {}

    def add(value):
        raw = value.encode("ascii")
        found = offsets.get(raw)
        if found is not None:
            return found, len(raw)
        offset = strings_base + len(strings)
        offsets[raw] = offset
        strings.extend(raw + b"\0")
        return offset, len(raw)

    path_offset, path_length = add(SOURCE)
    table_name_offset, table_name_length = add("NAVIMAP_USE")
    scalar_rows = bytearray()
    for name, value, active in scalars:
        name_offset, name_length = add(name)
        value_offset, value_length = add(value)
        scalar_rows.extend(SCALAR.pack(name_offset, name_length,
                                       value_offset, value_length, active))
    value_rows = bytearray()
    for value in values:
        offset, length = add(value)
        value_rows.extend(SPAN.pack(offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(strings), SOURCE_BYTES,
                         SOURCE_LINES, len(scalars), len(values), path_offset,
                         path_length, table_name_offset, table_name_length)
    return header + bytes(scalar_rows) + bytes(value_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    scalars, values = collect(args.dump)
    blob = build(scalars, values)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"source": SOURCE, "scalars": scalars,
                       "table_values": values}, stream, indent=2)
    print("%s: NavimapParam.lua, %d scalars and %d table values, %d bytes" %
          (args.out, len(scalars), len(values), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
