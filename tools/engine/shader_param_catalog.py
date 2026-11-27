r"""Pack numeric parameters from shipped per-car shader Lua files.

    python tools/engine/shader_param_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/shader_params.r6shp

Each data/car/shader/parameter/*_ShaderParameter.lua file declares a
ShaderParameterList with day/night environment pairs. Only paths, model names
and the 8 numeric values are copied as float32; no texture or shader binding
is inferred.
"""

import argparse
import glob
import json
import math
import os
import re
import struct

MAGIC = b"R6SHP\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<4I8f")
EXPECTED_FILES = 142
SUFFIX = "_ShaderParameter.lua"
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def table(text, marker):
    at = text.find(marker)
    if at < 0:
        raise ValueError("missing %s" % marker)
    start = text.find("{", at)
    if start < 0:
        raise ValueError("missing table after %s" % marker)
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
    raise ValueError("unterminated table after %s" % marker)


def collect(dump):
    root = os.path.join(dump, "data", "car", "shader", "parameter")
    paths = sorted(glob.glob(os.path.join(root, "*" + SUFFIX)))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d shader parameter files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    rows = []
    for path in paths:
        raw = open(path, "rb").read()
        text = raw.decode("cp932", errors="replace")
        clean = "\n".join(re.sub(r"--.*", "", line)
                          for line in text.splitlines())
        if "ShaderParameterList" not in clean:
            raise ValueError("missing ShaderParameterList: %s" % path)
        values = []
        for phase in ("day", "night"):
            body = table(clean, phase)
            body = table(body, "environment")
            found = [float(token) for token in NUMBER_RE.findall(body)]
            if len(found) != 4 or not all(math.isfinite(v) for v in found):
                raise ValueError("bad %s values: %s" % (phase, path))
            values.extend(found)
        name = os.path.basename(path)
        rows.append((os.path.relpath(path, dump).replace("\\", "/"),
                     name[:-len(SUFFIX)], values))
    return rows


def build(rows):
    strings_base = HEADER.size + len(rows) * FILE.size
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

    payload = bytearray()
    for path, model, values in rows:
        path_off, path_len = add(path)
        model_off, model_len = add(model)
        payload.extend(FILE.pack(path_off, path_len, model_off, model_len,
                                 *values))
    header = HEADER.pack(MAGIC, VERSION, len(rows), len(strings), 0, 0)
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
            json.dump([{"path": row[0], "model": row[1],
                        "values": row[2]} for row in rows], stream, indent=2)
    print("%s: %d shader parameter files, %d bytes" %
          (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
