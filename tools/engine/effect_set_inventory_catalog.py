r"""Pack shipped stage-effect SET_*.lua path/model inventory facts.

    python tools/engine/effect_set_inventory_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/effect_set_inventory.r6efs

Source paths, set names, num/EffectSetNum tokens and copied path/model strings
are packed. Float, transform and timing fields are not copied or interpreted.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6EFS\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
FILE = struct.Struct("<11I")
ROW = struct.Struct("<4I")
PATTERN = "data/effect/**/parameter/SET_*.lua"
EXPECTED_FILES = 300
EXPECTED_BYTES = 501917
EXPECTED_ROWS = 1899
NAME = re.compile(r'^\s*name\s+= "([^"]*)",\s*$')
PATH = re.compile(r'^\s*path\s+= "([^"]*)",\s*$')
MODEL = re.compile(r'^\s*model = "([^"]*)",\s*$')
NUM = re.compile(r'^\s*num = (-?\d+),\s*$')
EFFECT_NUM = re.compile(r'^EffectSetNum = (-?\d+)\s*$')


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/")),
                             recursive=True))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected SET_*.lua corpus")
    files = []
    row_total = 0
    for path in paths:
        raw = open(path, "rb").read()
        lines = raw.decode("ascii", errors="replace").splitlines()
        names = [m.group(1) for line in lines if (m := NAME.match(line))]
        nums = [m.group(1) for line in lines if (m := NUM.match(line))]
        effect_nums = [m.group(1) for line in lines
                       if (m := EFFECT_NUM.match(line))]
        row_paths = [m.group(1) for line in lines if (m := PATH.match(line))]
        row_models = [m.group(1) for line in lines
                      if (m := MODEL.match(line))]
        if len(names) != 1 or len(nums) != 1 or len(effect_nums) != 1 or \
                not row_paths or len(row_paths) != len(row_models):
            raise ValueError("bad SET_*.lua shape: " + path)
        for value in [names[0], nums[0], effect_nums[0]] + \
                row_paths + row_models:
            if len(value) > 96 or any(ord(ch) < 0x20 or ord(ch) > 0x7e
                                      for ch in value):
                raise ValueError("non-printable SET_*.lua token: " + path)
        relative = os.path.relpath(path, dump).replace("\\", "/")
        if len(relative) > 128:
            raise ValueError("long SET_*.lua source path: " + path)
        files.append((relative, len(raw), names[0], nums[0], effect_nums[0],
                      list(zip(row_paths, row_models))))
        row_total += len(row_paths)
    if row_total != EXPECTED_ROWS:
        raise ValueError("unexpected SET_*.lua row total")
    return files


def build(files):
    row_count = sum(len(row[5]) for row in files)
    strings_base = HEADER.size + len(files) * FILE.size + row_count * ROW.size
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
    name_rows = bytearray()
    row_base = 0
    for path, size, name, num, effect_num, rows in files:
        spans = [add(value) for value in (path, name, num, effect_num)]
        fields = []
        for offset, length in spans:
            fields.extend((offset, length))
        fields.extend((size, len(rows), row_base))
        file_rows.extend(FILE.pack(*fields))
        for row_path, row_model in rows:
            path_span = add(row_path)
            model_span = add(row_model)
            name_rows.extend(ROW.pack(path_span[0], path_span[1],
                                      model_span[0], model_span[1]))
        row_base += len(rows)
    header = HEADER.pack(MAGIC, VERSION, len(files), row_count,
                         len(strings), EXPECTED_BYTES)
    return header + bytes(file_rows) + bytes(name_rows) + bytes(strings)


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
            json.dump([{"path": row[0], "bytes": row[1], "name": row[2],
                        "num": row[3], "effect_set_num": row[4],
                        "rows": row[5]} for row in files], stream, indent=2)
    print("%s: %d set files, %d path/model rows, %d bytes" %
          (args.out, len(files), sum(len(row[5]) for row in files),
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
