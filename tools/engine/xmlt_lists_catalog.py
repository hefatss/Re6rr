r"""Pack shipped XMLT list, seed and field-tag structure.

    python tools/engine/xmlt_lists_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/xmlt_lists.r6xlt

Every data_jp/scene/**/*.xmlt file is parsed with the shipped-format regexes
already used by story_catalog.py. Paths, LIST_TYPE names, seed counts and
field-tag occurrences are copied. Text values, timing, BGM and unlock
semantics are not inferred.
"""

import argparse
import glob
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_catalog as sc  # noqa: E402

MAGIC = b"R6XLT\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s9I")
FILE = struct.Struct("<4I")
LIST = struct.Struct("<5I")
SEED = struct.Struct("<3I")
FIELD = struct.Struct("<2I")
EXPECTED_FILES = 591
EXPECTED_LISTS = 3482
EXPECTED_SEEDS = 4432
EXPECTED_FIELDS = 16544
EXPECTED_TYPES = 25
EXPECTED_TAGS = 30
ASSETS_REPORT = os.path.join(ROOT, "docs", "recon", "assets.json")


def collect(dump, assets=ASSETS_REPORT):
    root = os.path.join(dump, "data_jp", "scene")
    paths = sorted(glob.glob(os.path.join(root, "**", "*.xmlt"),
                             recursive=True))
    if len(paths) != EXPECTED_FILES:
        raise ValueError("expected %d XMLT files, found %d" %
                         (EXPECTED_FILES, len(paths)))
    with open(assets, "r", encoding="utf8") as stream:
        report = json.load(stream)
    found = []

    def visit(node):
        if isinstance(node, dict):
            if node.get("ext") == ".xmlt":
                found.append(node)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(report)
    if len(found) != 1 or found[0]["files"] != EXPECTED_FILES or \
            found[0]["bytes"] != 999619:
        raise ValueError("XMLT counts disagree with assets.json")

    raw = []
    types = set()
    tags = set()
    for path in paths:
        lists = []
        for list_type, body in sc.LIST_RE.findall(sc.read_text(path)):
            if not list_type.isascii() or not list_type:
                raise ValueError("bad LIST_TYPE in %s" % path)
            types.add(list_type)
            seeds = []
            for seed in sc.SEED_RE.findall(body):
                keys = [key for key, _ in sc.FIELD_RE.findall(seed)]
                if not keys or any(not key.isascii() for key in keys):
                    raise ValueError("bad field tag in %s" % path)
                tags.update(keys)
                seeds.append(keys)
            lists.append((list_type, seeds))
        raw.append((os.path.relpath(path, dump).replace("\\", "/"), lists))
    if (len(types), len(tags)) != (EXPECTED_TYPES, EXPECTED_TAGS):
        raise ValueError("expected %d types/%d tags, found %d/%d" %
                         (EXPECTED_TYPES, EXPECTED_TAGS, len(types),
                          len(tags)))

    type_names = sorted(types)
    tag_names = sorted(tags)
    type_index = {name: at for at, name in enumerate(type_names)}
    tag_index = {name: at for at, name in enumerate(tag_names)}
    files = []
    lists = []
    seeds = []
    fields = []
    for path, blocks in raw:
        first_list = len(lists)
        for list_type, blocks_seeds in blocks:
            first_seed = len(seeds)
            first_field = len(fields)
            for keys in blocks_seeds:
                seed_index = len(seeds)
                seed_field = len(fields)
                for key in keys:
                    fields.append((seed_index, tag_index[key]))
                seeds.append((len(lists), seed_field, len(keys)))
            lists.append((type_index[list_type], first_seed,
                          len(seeds) - first_seed, first_field,
                          len(fields) - first_field))
        files.append((path, first_list, len(lists) - first_list))
    if (len(lists), len(seeds), len(fields)) != (EXPECTED_LISTS,
                                                 EXPECTED_SEEDS,
                                                 EXPECTED_FIELDS):
        raise ValueError("unexpected list/seed/field counts %d/%d/%d" %
                         (len(lists), len(seeds), len(fields)))
    return files, lists, seeds, fields, type_names, tag_names


def build(files, lists, seeds, fields, type_names, tag_names):
    strings_base = (HEADER.size + len(files) * FILE.size +
                    len(lists) * LIST.size + len(seeds) * SEED.size +
                    len(fields) * FIELD.size)
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
    for path, first, count in files:
        offset, length = add(path)
        file_rows.extend(FILE.pack(offset, length, first, count))
    list_rows = b"".join(LIST.pack(*row) for row in lists)
    seed_rows = b"".join(SEED.pack(*row) for row in seeds)
    field_rows = b"".join(FIELD.pack(*row) for row in fields)
    for name in type_names:
        add(name)
    for name in tag_names:
        add(name)
    header = HEADER.pack(MAGIC, VERSION, len(files), len(lists), len(seeds),
                         len(fields), len(type_names), len(tag_names),
                         len(strings), 0)
    return header + bytes(file_rows) + list_rows + seed_rows + field_rows + \
        bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--assets", default=ASSETS_REPORT)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, lists, seeds, fields, types, tags = collect(args.dump, args.assets)
    blob = build(files, lists, seeds, fields, types, tags)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"files": files, "types": types, "tags": tags,
                       "list_count": len(lists), "seed_count": len(seeds),
                       "field_count": len(fields)}, stream, indent=2)
    print("%s: %d files, %d lists, %d seeds, %d fields, %d bytes" %
          (args.out, len(files), len(lists), len(seeds), len(fields),
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
