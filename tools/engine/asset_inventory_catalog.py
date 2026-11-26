"""Pack shipped asset-tree counts into an R6AIV blob.

    python tools/engine/asset_inventory_catalog.py \
        --out build/tmp/asset_inventory.r6aiv

Rows come from docs/recon/assets.json: extension counts, inner magic counts,
top folders and 40 shader samples. No dump data is committed.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "assets.json")

MAGIC = b"R6AIV\0\1\0"
VERSION = 1
KINDS = ("text", "raw", "gzip", "XMD", "NTWD", "zeros", "ZIP")
HEADER = struct.Struct("<8s13I")
EXT = struct.Struct("<IIIQ7I")
MAGIC_ROW = struct.Struct("<3I")
FOLDER = struct.Struct("<IIIQ")
SHADER = struct.Struct("<2I16s")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    exts = []
    magics = []
    folders = []
    shaders = []
    roots = []
    for root_index, item in enumerate(data["roots"]):
        roots.append(item["classified"])
        for ext in item["extensions"]:
            assert set(ext["kinds"]) <= set(KINDS), ext["ext"]
            exts.append({
                "root": root_index, "name": ext["ext"],
                "files": ext["files"], "bytes": ext["bytes"],
                "kinds": [ext["kinds"].get(kind, 0) for kind in KINDS],
            })
        for name, count in item["inner_magics"]:
            magics.append({"root": root_index, "name": name,
                           "count": count})
        for folder in item["top_folders"]:
            folders.append({
                "root": root_index, "name": folder["name"],
                "files": folder["files"], "bytes": folder["bytes"],
            })
        for sample in item["shader_samples"]:
            assert sample["kind"] == "text" and sample["inner"] is None
            shaders.append({
                "path": sample["path"], "size": sample["size"],
                "head": bytes.fromhex(sample["head"]),
            })
            assert len(shaders[-1]["head"]) == 16
    assert len(roots) == 2 and len(exts) == 32
    assert len(magics) == 7 and len(folders) == 27
    assert len(shaders) == 40
    return roots, exts, magics, folders, shaders


def build(roots, exts, magics, folders, shaders):
    ext_off = HEADER.size
    magic_off = ext_off + EXT.size * len(exts)
    folder_off = magic_off + MAGIC_ROW.size * len(magics)
    shader_off = folder_off + FOLDER.size * len(folders)
    strings_off = shader_off + SHADER.size * len(shaders)
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    ext_payload = b"".join(
        EXT.pack(row["root"], add(row["name"]), row["files"], row["bytes"],
                 *row["kinds"])
        for row in exts)
    magic_payload = b"".join(
        MAGIC_ROW.pack(row["root"], add(row["name"]), row["count"])
        for row in magics)
    folder_payload = b"".join(
        FOLDER.pack(row["root"], add(row["name"]), row["files"], row["bytes"])
        for row in folders)
    shader_payload = b"".join(
        SHADER.pack(add(row["path"]), row["size"], row["head"])
        for row in shaders)

    return (HEADER.pack(
        MAGIC, VERSION, 2, roots[0], roots[1], 19, 13, 4, 3, 14, 13,
        len(shaders), strings_off, len(strings)) +
        ext_payload + magic_payload + folder_payload + shader_payload +
        bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    roots, exts, magics, folders, shaders = collect(args.report)
    blob = build(roots, exts, magics, folders, shaders)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: 2 roots, %d extensions, %d magics, %d folders, %d shader "
          "samples, %d bytes" % (args.out, len(exts), len(magics),
                                 len(folders), len(shaders), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
