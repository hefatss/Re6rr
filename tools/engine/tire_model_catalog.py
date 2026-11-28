r"""Pack shipped per-car TireInfo.lua integer, name and enum facts.

    python tools/engine/tire_model_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/tire_model.r6tir

Paths, TIRE_* model names, WHEEL_SCALE_*/TIRE_WIDTH_SCALE_* tokens,
wheel_default strings and wheel_color integers are copied. Float fields,
CP932 comments and tuning behavior are not decoded.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6TIR\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<8I")
SPAN = struct.Struct("<2I")
PATTERN = "data/car/tire/model_type/TireModelType_*.lua"
EXPECTED_FILES = 240
EXPECTED_BYTES = 165906
EXPECTED_LINES = 7201
GROUPS = ("inc_normal", "inc_size_up", "wheel_scale", "tire_width")
QUOTED = re.compile(r'^\s*"([A-Za-z0-9_]+)",')
TOKEN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*|1\.0)\s*,")
DEFAULT = re.compile(r'^\s*wheel_default\s*=\s*"([A-Za-z0-9_]+)",')
COLOR = re.compile(r"^\s*wheel_color\s*=\s*(\d+),")
MARKER = re.compile(r"^\s*(\w+)\s*=\s*\{\s*$")
END = re.compile(r"^\s*\},\s*$")


def section(lines, name):
    start = next((index for index, line in enumerate(lines)
                  if line.strip() == name + " = {"), None)
    if start is None:
        raise ValueError("missing TireInfo section: " + name)
    rows = []
    for line in lines[start + 1:]:
        if END.match(line):
            break
        rows.append(line)
    if len(rows) != 4:
        raise ValueError("bad TireInfo section length: " + name)
    return rows


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/"))))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(p) for p in paths) != EXPECTED_BYTES or \
            sum(open(p, "rb").read().count(b"\n") for p in paths) != \
            EXPECTED_LINES:
        raise ValueError("unexpected TireInfo corpus")
    files = []
    spans = []
    for path in paths:
        raw = open(path, "rb").read()
        # CP932 comments are dropped; only printable ASCII rows are read.
        text = raw.decode("ascii", errors="replace")
        lines = text.splitlines()
        values = []
        for name in GROUPS:
            for line in section(lines, name):
                if name in ("inc_normal", "inc_size_up"):
                    match = QUOTED.match(line)
                    if not match:
                        raise ValueError("bad TireInfo model: " + path)
                    values.append(match.group(1))
                else:
                    match = TOKEN.match(line)
                    if not match:
                        raise ValueError("bad TireInfo enum: " + path)
                    values.append(match.group(1) if match.group(1) != "1.0"
                                  else "")
        default = [m.group(1) for line in lines if (m := DEFAULT.match(line))]
        color = [int(m.group(1)) for line in lines if (m := COLOR.match(line))]
        if len(default) != 1 or len(color) != 1 or color[0] > 4:
            raise ValueError("bad TireInfo scalar: " + path)
        for value in values:
            if any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in value):
                raise ValueError("bad TireInfo token: " + path)
        relative = os.path.relpath(path, dump).replace("\\", "/")
        base = len(spans)
        spans.extend(values)
        files.append((relative, len(raw), len(lines), base,
                      default[0], color[0]))
    if len(spans) != EXPECTED_FILES * 16:
        raise ValueError("unexpected TireInfo span count")
    return files, spans


def build(files, spans):
    strings_base = HEADER.size + len(files) * FILE.size + \
        len(spans) * SPAN.size
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
    for path, size, lines, base, default, color in files:
        span = add(path)
        default_span = add(default)
        file_rows.extend(FILE.pack(span[0], span[1], size, lines, base,
                                   default_span[0], default_span[1], color))
    span_rows = bytearray()
    for value in spans:
        if value:
            span = add(value)
            span_rows.extend(SPAN.pack(span[0], span[1]))
        else:
            span_rows.extend(SPAN.pack(0, 0))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(spans),
                         len(strings), sum(row[1] for row in files))
    return header + bytes(file_rows) + bytes(span_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, spans = collect(args.dump)
    blob = build(files, spans)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": files, "spans": spans}, stream, indent=2)
    print("%s: %d TireInfo files, %d spans, %d bytes" %
          (args.out, len(files), len(spans), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
