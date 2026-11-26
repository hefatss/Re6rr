"""Compile reflected vertex inputs into a C-readable layout blob.

    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --glsl-dir build/tmp/glsl
    python tools/engine/vertex_layout.py \
        --manifest build/tmp/glsl/manifest.json --out build/tmp/glsl/vertex.r6gv

Vertex records follow the explicit `layout(location=N)` emitted by
`nsxr_shader.glsl_es_source()`. No mesh-to-attribute mapping is invented: the
host decides which vertex buffer fills each semantic.
"""

import argparse
import json
import os
import struct

MAGIC = b"R6GV"
VERSION = 1
HEADER = struct.Struct("<4sHHIIII")
RECORD = struct.Struct("<IHHHHI")


def build(manifest):
    entries = manifest["shaders"] if isinstance(manifest, dict) else manifest
    items = []
    for entry in entries:
        bindings = entry["bindings"]
        if bindings["stage"] != "vertex":
            continue
        for item in bindings["inputs"]:
            items.append((entry["shader"], item["register"],
                          item["semantic_index"], item["mask"],
                          item["semantic"]))

    string_off = HEADER.size + len(items) * RECORD.size
    strings = bytearray(b"\0")
    offsets = {b"": string_off}

    def intern(value):
        encoded = value.encode("utf8") + b"\0"
        if encoded not in offsets:
            offsets[encoded] = string_off + len(strings)
            strings.extend(encoded)
        return offsets[encoded]

    records = bytearray()
    for shader, register, semantic_index, mask, semantic in items:
        records.extend(RECORD.pack(intern(shader), register, semantic_index,
                                   mask, 0, intern(semantic)))

    return HEADER.pack(MAGIC, VERSION, 0, len(items), string_off, 0, 0) + \
        bytes(records) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with open(args.manifest, encoding="utf8") as stream:
        manifest = json.load(stream)
    blob = build(manifest)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d vertex attributes, %d bytes" %
          (args.out, HEADER.unpack_from(blob)[3], len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
