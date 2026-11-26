"""Pack shipped executable and source path strings into an R6PST blob.

    python tools/engine/path_strings_catalog.py \
        --out build/tmp/path_strings.r6pst

Facts come from docs/recon/exe_paths.json and source_paths.json: 1,271
executable strings and 422 source file paths. No executable bytes are copied.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EXE_REPORT = os.path.join(ROOT, "docs", "recon", "exe_paths.json")
SOURCE_REPORT = os.path.join(ROOT, "docs", "recon", "source_paths.json")

MAGIC = b"R6PST\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s4I")
GROUP = struct.Struct("<3I")
WORD = struct.Struct("<I")
EXE = 0
SOURCE = 1


def collect(exe_report=EXE_REPORT, source_report=SOURCE_REPORT):
    with open(exe_report, "r", encoding="utf8") as stream:
        exe = json.load(stream)
    with open(source_report, "r", encoding="utf8") as stream:
        source = json.load(stream)
    assert len(exe) == 1271 and len(source) == 422
    assert all(isinstance(item, str) for item in exe + source)
    return [exe, source]


def build(groups):
    string_off = HEADER.size + GROUP.size * len(groups) + \
        WORD.size * sum(len(group) for group in groups)
    strings = bytearray()

    def add(value):
        offset = string_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    offsets = [add(value) for group in groups for value in group]
    first = 0
    group_payload = bytearray()
    for kind, group in enumerate(groups):
        group_payload.extend(GROUP.pack(kind, len(group), first))
        first += len(group)

    header = HEADER.pack(MAGIC, VERSION, len(groups), len(offsets),
                         len(strings))
    return (header + bytes(group_payload) +
            b"".join(WORD.pack(offset) for offset in offsets) +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=EXE_REPORT)
    parser.add_argument("--source", default=SOURCE_REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    groups = collect(args.exe, args.source)
    blob = build(groups)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: 1271 executable and 422 source strings, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
