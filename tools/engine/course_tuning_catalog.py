r"""Pack shipped course tuning integer maps and ASCII symbol names.

    python tools/engine/course_tuning_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/course_tuning.r6ctn

Source paths, table globals, ordinal integer rows and copied ASCII GID/ramp/
stage symbol names are packed. CP932 header comments are not decoded and no
tuning semantics are inferred.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6CTN\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<8I")
RAMP_ROW = struct.Struct("<8I")
TA_ROW = struct.Struct("<5I")
NAMES = ("RampParam.lua", "TAParam.lua")
EXPECTED_BYTES = 5267
EXPECTED_RAMP = 39
EXPECTED_TA = 25
RAMP_GLOBAL = re.compile(r"^RAMP_PARAM\s*=\s*\{\s*$")
TA_GLOBAL = re.compile(r"^TA_PARAM\s*=\s*\{\s*$")
RAMP_ROW_RE = re.compile(
    r"^\s*\{\s*(\d+),\s*(\d+),\s*\},\s*--\s*(GID_\w+)\s*,\s*(ERamp_\w+)"
    r"(?:\s*==\s*(ERamp_\w+))?")
TA_ROW_RE = re.compile(
    r"^\s*(\d+),\s*--\s*game::(GID_\w+)\s*,\s*((?:EStage_TA_|ERamp_)\w+)?")


def collect(dump):
    base = os.path.join(dump, "data", "course", "parameter", "tuning")
    paths = [os.path.join(base, name) for name in NAMES]
    if sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected course tuning corpus")
    raw_files = [open(path, "rb").read() for path in paths]
    ramp_text = raw_files[0].decode("ascii", errors="replace")
    ta_text = raw_files[1].decode("ascii", errors="replace")
    ramp_lines = ramp_text.splitlines()
    ta_lines = ta_text.splitlines()
    if not any(RAMP_GLOBAL.match(line) for line in ramp_lines) or \
            not any(TA_GLOBAL.match(line) for line in ta_lines):
        raise ValueError("missing tuning table global")
    ramp = []
    for line in ramp_lines:
        match = RAMP_ROW_RE.match(line)
        if match:
            normal, extreme, gid, name, alias = match.groups()
            ramp.append((int(normal), int(extreme), gid, name, alias or ""))
    ta = []
    for line in ta_lines:
        match = TA_ROW_RE.match(line)
        if match:
            value, gid, name = match.groups()
            ta.append((int(value), gid, name or ""))
    if len(ramp) != EXPECTED_RAMP or len(ta) != EXPECTED_TA:
        raise ValueError("unexpected tuning row totals")
    for value, _, _, _, _ in ramp:
        if value > 9999:
            raise ValueError("out-of-range RAMP_PARAM value")
    for value, _, _ in ta:
        if value > 9999:
            raise ValueError("out-of-range TA_PARAM value")
    files = [
        ("data/course/parameter/tuning/RampParam.lua", len(raw_files[0]),
         len(ramp_lines), "RAMP_PARAM", ramp),
        ("data/course/parameter/tuning/TAParam.lua", len(raw_files[1]),
         len(ta_lines), "TA_PARAM", ta),
    ]
    return files


def build(files):
    strings_base = HEADER.size + len(files) * FILE.size + \
        EXPECTED_RAMP * RAMP_ROW.size + EXPECTED_TA * TA_ROW.size
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

    file_rows = bytearray()
    ramp_rows = bytearray()
    ta_rows = bytearray()
    ramp_base = 0
    for path, size, lines, global_name, rows in files:
        path_span = add(path)
        global_span = add(global_name)
        row_base = ramp_base if global_name == "RAMP_PARAM" else 0
        file_rows.extend(FILE.pack(path_span[0], path_span[1], size, lines,
                                   global_span[0], global_span[1], row_base,
                                   len(rows)))
        if global_name == "RAMP_PARAM":
            for normal, extreme, gid, name, alias in rows:
                g = add(gid)
                n = add(name)
                a = add(alias)
                ramp_rows.extend(RAMP_ROW.pack(
                    normal, extreme, g[0], g[1], n[0], n[1], a[0], a[1]))
            ramp_base = len(rows)
        else:
            for value, gid, name in rows:
                g = add(gid)
                n = add(name)
                ta_rows.extend(TA_ROW.pack(value, g[0], g[1], n[0], n[1]))
    header = HEADER.pack(MAGIC, VERSION, len(files), EXPECTED_RAMP,
                         EXPECTED_TA, len(strings), EXPECTED_BYTES)
    return header + bytes(file_rows) + bytes(ramp_rows) + \
        bytes(ta_rows) + bytes(strings)


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
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump([{"path": entry[0], "bytes": entry[1],
                        "lines": entry[2], "global": entry[3],
                        "rows": entry[4]} for entry in files], stream,
                      indent=2)
    print("%s: 2 tuning files, %d ramp rows, %d TA rows, %d bytes" %
          (args.out, EXPECTED_RAMP, EXPECTED_TA, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
