"""Index the global functions defined by the WMMT6RR data scripts.

    python tools/lua/script_sets.py --dump D:\\Games\\W6W-05 --name GetTirePos

The game overwrites globals as it loads script sets, so knowing which file
defines a function (and how many files do) is needed to reproduce a context.
Only top-level-looking definitions are indexed; `local function` is ignored.
"""

import argparse
import collections
import gzip
import json
import os
import re
import sys

DEFINE = re.compile(
    r"^[ \t]*(?:function[ \t]+([A-Za-z_]\w*)[ \t]*\("
    r"|([A-Za-z_]\w*)[ \t]*=[ \t]*function[ \t]*\()",
    re.MULTILINE)


def read_script(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:3] == b"\x1f\x8b\x08":
        raw = gzip.decompress(raw)
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("cp932", "replace")


def build_index(dump):
    index = collections.defaultdict(list)
    root = os.path.join(dump, "data")
    for base, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".lua"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, dump)
            for match in DEFINE.finditer(read_script(path)):
                global_name = match.group(1) or match.group(2)
                if global_name not in index[global_name]:
                    index[global_name].append(rel)
    for paths in index.values():
        paths.sort()
    return dict(index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                     r"D:\Games\W6W-05"))
    ap.add_argument("--name", action="append", default=[],
                    help="print the files defining this global")
    ap.add_argument("--bindings", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "docs", "recon", "bindings.json"))
    ap.add_argument("--json", metavar="PATH", help="write the whole index")
    args = ap.parse_args()

    index = build_index(args.dump)
    if args.json:
        with open(args.json, "w", encoding="utf8") as f:
            json.dump(index, f, ensure_ascii=False, indent=1)
        print("indexed %d globals into %s" % (len(index), args.json))
    if args.name:
        for name in args.name:
            paths = index.get(name, [])
            print("%s: %d files" % (name, len(paths)))
            for path in paths[:40]:
                print("  %s" % path)
            if len(paths) > 40:
                print("  ...")
    elif os.path.exists(args.bindings):
        names = json.load(open(args.bindings, encoding="utf8"))
        unique = [n for n in names if len(index.get(n, [])) == 1]
        ambiguous = [n for n in names if len(index.get(n, [])) > 1]
        undeclared = [n for n in names if not index.get(n)]
        print("bindings=%d unique=%d ambiguous=%d no_definition=%d" % (
            len(names), len(unique), len(ambiguous), len(undeclared)))
        print("no_definition=%s" % undeclared[:20])
        print("examples unique=%s" % [(n, index[n][0]) for n in unique[:10]])
        print("examples ambiguous=%s" % [
            (n, len(index[n])) for n in ambiguous[:10]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
