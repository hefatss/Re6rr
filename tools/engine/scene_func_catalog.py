r"""Pack shipped scene function-name and return-expression facts.

    python tools/engine/scene_func_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/scene_func.r6sfn

Paths, function names and copied ASCII return expressions are packed. CP932
comments, scene logic and data payloads are not interpreted.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6SFN\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<6I")
FUNC = struct.Struct("<4I")
PATTERN = "data_jp/scene/func/Func_*.Lua"
EXPECTED_BYTES = 4289
EXPECTED_COUNTS = (8, 12, 23)
FUNCTION = re.compile(r"^function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)")
RETURN = re.compile(r"^\s*return\s+(.+?);?\s*$")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/")),
                             recursive=True))
    if len(paths) != 3 or sum(os.path.getsize(p) for p in paths) != \
            EXPECTED_BYTES:
        raise ValueError("unexpected scene func corpus")
    files = []
    functions = []
    for path, count in zip(paths, EXPECTED_COUNTS):
        raw = open(path, "rb").read()
        text = raw.decode("ascii", errors="replace")
        lines = text.splitlines()
        rows = []
        for index, line in enumerate(lines):
            match = FUNCTION.match(line)
            if not match:
                continue
            result = next((RETURN.match(item).group(1)
                           for item in lines[index + 1:]
                           if RETURN.match(item)), None)
            if result is None:
                raise ValueError("missing scene func return: " + path)
            rows.append((match.group(1), result.strip()))
        if len(rows) != count:
            raise ValueError("bad scene func count: " + path)
        relative = os.path.relpath(path, dump).replace("\\", "/")
        for name, result in rows:
            if any(ord(ch) < 0x20 or ord(ch) > 0x7e
                   for ch in name + result):
                raise ValueError("non-printable scene func: " + path)
        files.append((relative, len(raw), len(lines), rows))
        functions.extend(rows)
    if len(functions) != sum(EXPECTED_COUNTS):
        raise ValueError("unexpected scene func total")
    return files


def build(files):
    functions = [row for entry in files for row in entry[3]]
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
    function_rows = bytearray()
    function_base = 0
    for path, size, lines, rows in files:
        span = add(path)
        file_rows.extend(FILE.pack(span[0], span[1], size, lines,
                                   function_base, len(rows)))
        for name, result in rows:
            name_span = add(name)
            result_span = add(result)
            function_rows.extend(FUNC.pack(name_span[0], name_span[1],
                                           result_span[0], result_span[1]))
        function_base += len(rows)
    header = HEADER.pack(MAGIC, VERSION, len(files), len(functions),
                         len(strings), EXPECTED_BYTES)
    return header + bytes(file_rows) + bytes(function_rows) + bytes(strings)


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
                        "lines": entry[2], "functions": entry[3]}
                       for entry in files], stream, indent=2)
    print("%s: 3 scene func files, %d definitions, %d bytes" %
          (args.out, sum(len(entry[3]) for entry in files), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
