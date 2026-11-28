r"""Pack shipped Lua accessor script function facts.

    python tools/engine/accessor_script_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/accessor_script.r6acc

Paths, function names, argument lists, first return expressions and line
positions are copied. CP932 comments, unpack semantics and render/tuning
behavior are not decoded.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6ACC\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<7I")
FUNC = struct.Struct("<7I")
PATHS = (
    ("data/course/script/AreaAccessor.lua", 4183, 180, 32, 32),
    ("data/course/script/ParamAccessor.lua", 6379, 266, 38, 46),
    ("data/course/script/SectionAccessor.lua", 13727, 406, 22, 60),
    ("data/course/script/StageAccessor.lua", 7102, 281, 48, 49),
    ("data/car/shader/script/ShaderAccessor.lua", 506, 15, 1, 1),
    ("data/car/tire/script/TireAccessor.lua", 879, 31, 9, 9),
    ("data/effect/stage_effect/script/EffectSetTool.lua", 2480, 111, 5, 20),
)
EXPECTED_BYTES = 35256
EXPECTED_LINES = 1290
FUNC_LINE = re.compile(r"^function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)")
RETURN_LINE = re.compile(r"^\s*return\b(.*)$")


def clean(value):
    value = value.split("--", 1)[0].strip()
    if any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in value):
        raise ValueError("non-ASCII accessor token")
    return value


def collect(dump):
    files = []
    functions = []
    for relative, size, count, funcs, rets in PATHS:
        path = os.path.join(dump, *relative.split("/"))
        raw = open(path, "rb").read()
        if len(raw) != size or raw.count(b"\n") != count:
            raise ValueError("unexpected accessor source: " + relative)
        text = raw.decode("ascii", errors="replace")
        lines = text.splitlines()
        rows = []
        for index, line in enumerate(lines):
            match = FUNC_LINE.match(line)
            if not match:
                continue
            result = None
            for following in lines[index + 1:]:
                ret = RETURN_LINE.match(following)
                if ret:
                    result = clean(ret.group(1))
                    break
                if FUNC_LINE.match(following):
                    break
            rows.append((clean(match.group(1)), clean(match.group(2)),
                         result, index))
        if len(rows) != funcs or \
                sum(1 for line in lines if RETURN_LINE.match(line)) != rets:
            raise ValueError("unexpected accessor functions: " + relative)
        base = len(functions)
        functions.extend(rows)
        files.append((relative, size, count, base, len(rows), rets))
    if sum(row[1] for row in files) != EXPECTED_BYTES or \
            sum(row[2] for row in files) != EXPECTED_LINES:
        raise ValueError("unexpected accessor corpus")
    return files, functions


def build(files, functions):
    strings_base = HEADER.size + len(files) * FILE.size + \
        len(functions) * FUNC.size
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
    for path, size, lines, base, count, rets in files:
        span = add(path)
        file_rows.extend(FILE.pack(span[0], span[1], size, lines,
                                   base, count, rets))
    func_rows = bytearray()
    for name, args, result, line in functions:
        name_span = add(name)
        args_span = add(args)
        result_span = add(result or "")
        func_rows.extend(FUNC.pack(name_span[0], name_span[1],
                                   args_span[0], args_span[1],
                                   result_span[0], result_span[1], line))
    header = HEADER.pack(MAGIC, VERSION, len(files), len(functions),
                         len(strings), EXPECTED_BYTES)
    return header + bytes(file_rows) + bytes(func_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, functions = collect(args.dump)
    blob = build(files, functions)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": files, "functions": functions}, stream,
                      indent=2)
    print("%s: 7 accessor scripts, 155 functions, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
