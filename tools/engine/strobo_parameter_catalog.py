r"""Pack shipped StroboLightOnOffParameter.lua integer and name facts.

    python tools/engine/strobo_parameter_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/strobo_parameter.r6slo

Source path, DEBUG_CODE, two integer-pair tables and four accessor names are
copied. CP932 comments and timing/rendering behavior are not interpreted.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6SLO\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s7I")
FILE = struct.Struct("<8I")
TABLE = struct.Struct("<4I")
ROW = struct.Struct("<2I")
SPAN = struct.Struct("<2I")
RELATIVE = "data/car/position/StroboLightOnOffParameter.lua"
EXPECTED_BYTES = 3771
EXPECTED_LINES = 95
TABLE_NAMES = ("StroboAeroList", "StroboRoofList")
EXPECTED_ROWS = (5, 3)
FUNCTIONS = ("GetStroboAeroListNumber", "GetStroboAeroList",
             "GetStroboRoofListNumber", "GetStroboRoofList")
DEBUG = re.compile(r"^DEBUG_CODE\s*=\s*(\d+)\s*$")
FUNCTION = re.compile(r"^function\s+([A-Za-z_]\w*)\s*\(")
PAIR = re.compile(r"^\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*\}")


def collect(dump):
    path = os.path.join(dump, *RELATIVE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != EXPECTED_BYTES or raw.count(b"\n") != EXPECTED_LINES:
        raise ValueError("unexpected Strobo parameter source")
    text = raw.decode("ascii", errors="replace")
    lines = text.splitlines()
    debug = [int(m.group(1)) for line in lines if (m := DEBUG.match(line))]
    functions = [m.group(1) for line in lines if (m := FUNCTION.match(line))]
    if debug != [0] or tuple(functions) != FUNCTIONS:
        raise ValueError("bad Strobo debug or function list")
    tables = []
    for name, count in zip(TABLE_NAMES, EXPECTED_ROWS):
        marker = next((index for index, line in enumerate(lines)
                       if line.startswith(name + " = {")), None)
        if marker is None:
            raise ValueError("missing Strobo table: " + name)
        rows = []
        for line in lines[marker + 1:]:
            if line.strip() == "}":
                break
            match = PAIR.match(line)
            if match:
                rows.append((int(match.group(1)), int(match.group(2))))
        if len(rows) != count:
            raise ValueError("bad Strobo row count: " + name)
        tables.append((name, rows))
    return RELATIVE, len(raw), len(lines), debug[0], tables, list(functions)


def build(entry):
    path, size, lines, debug, tables, functions = entry
    rows = [row for _, pairs in tables for row in pairs]
    strings_base = HEADER.size + FILE.size + len(tables) * TABLE.size + \
        len(rows) * ROW.size + len(functions) * SPAN.size
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

    path_span = add(path)
    table_rows = bytearray()
    row_rows = bytearray()
    row_base = 0
    for name, pairs in tables:
        span = add(name)
        table_rows.extend(TABLE.pack(span[0], span[1], row_base, len(pairs)))
        for first, second in pairs:
            row_rows.extend(ROW.pack(first, second))
        row_base += len(pairs)
    function_rows = bytearray()
    for name in functions:
        span = add(name)
        function_rows.extend(SPAN.pack(span[0], span[1]))
    header = HEADER.pack(MAGIC, VERSION, 1, len(tables), len(rows),
                         len(functions), len(strings), EXPECTED_BYTES)
    return header + FILE.pack(path_span[0], path_span[1], size, lines, debug,
                              0, row_base, 0) + bytes(table_rows) + \
        bytes(row_rows) + bytes(function_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    entry = collect(args.dump)
    blob = build(entry)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"path": entry[0], "bytes": entry[1], "lines": entry[2],
                       "debug": entry[3], "tables": entry[4],
                       "functions": entry[5]}, stream, indent=2)
    print("%s: 1 Strobo file, 2 tables, 8 rows, 4 functions, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
