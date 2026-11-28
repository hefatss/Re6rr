r"""Pack shipped event-scene hide-clip model-name facts.

    python tools/engine/event_scene_hide_clip_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/event_scene_hide_clip.r6ehc

Source byte sizes, copied ASCII model names and the one accessor name are
packed. No scene timing, visibility or gameplay semantics are inferred.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6EHC\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
SPAN = struct.Struct("<2I")
TABLE = "data/course/event_scene/EVENT_SCENE_HIDECLIP_ENDING.lua"
ACCESSOR = "data/course/script/EventSceneAccessor.lua"
TABLE_SIZE = 250
ACCESSOR_SIZE = 553
EXPECTED_NAMES = 4
ACCESSOR_NAME = "EventSceneHideClip_GetHideModel"


def collect(dump):
    table_path = os.path.join(dump, *TABLE.split("/"))
    accessor_path = os.path.join(dump, *ACCESSOR.split("/"))
    table_raw = open(table_path, "rb").read()
    accessor_raw = open(accessor_path, "rb").read()
    if len(table_raw) != TABLE_SIZE or len(accessor_raw) != ACCESSOR_SIZE:
        raise ValueError("unexpected event-scene source sizes")
    text = table_raw.decode("cp932", errors="replace")
    match = re.search(r"EVENT_SCENE_HIDECLIP_ENDING\s*=\s*\{(.*?)\}", text,
                      re.S)
    if not match:
        raise ValueError("missing EVENT_SCENE_HIDECLIP_ENDING table")
    names = re.findall(r'"([^"]+)"', match.group(1))
    functions = re.findall(r"function\s+([A-Za-z_]\w*)",
                           accessor_raw.decode("cp932", errors="replace"))
    if len(names) != EXPECTED_NAMES or len(set(names)) != len(names) or \
            functions != [ACCESSOR_NAME] or \
            any(not name.isascii() or not name.isprintable() or
                not name.startswith("OSAKA_NGT_NML_")
                for name in names):
        raise ValueError("unexpected event-scene hide-clip facts")
    return names, functions


def build(collection):
    names, functions = collection
    strings_base = HEADER.size + (len(names) + len(functions)) * SPAN.size
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

    spans = bytearray()
    for name in names + functions:
        offset, length = add(name)
        spans.extend(SPAN.pack(offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(names), len(strings),
                         TABLE_SIZE, ACCESSOR_SIZE)
    return header + bytes(spans) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    collection = collect(args.dump)
    blob = build(collection)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"names": collection[0], "functions": collection[1]},
                      stream, indent=2)
    print("%s: %d hide-clip names, 1 accessor, %d bytes" %
          (args.out, len(collection[0]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
