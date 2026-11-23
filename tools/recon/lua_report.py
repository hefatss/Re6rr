"""Inventory the game's Lua 5.1 scripts and list what they ask of the engine.

    python tools/recon/lua_report.py [--game PATH] [--out DIR]

The game keeps most of its data and flow in data/**/*.lua (4k+ files). This tool
answers, without running anything:

* how many scripts each folder holds and how big they are;
* which names the scripts define (so the engine does not have to provide them);
* which names they call but nothing defines - the candidate native API surface
  the port must implement as C bindings;
* which ``require``/module imports appear, and how often C-style calls mix with
  table methods.

Writes <out>/lua.json and prints a summary.
"""

import argparse
import collections
import json
import os
import re
import sys

DEF_RE = re.compile(
    r"(?:^|[^\w.:])function\s+([A-Za-z_][\w.:]*)"          # function a.b.c(
    r"|(?:^|[^\w.:])(?:local\s+)?([A-Za-z_][\w.]*)\s*=\s*function"  # x = function
    r"|(?:^|[^\w.:])(?:local\s+)?([A-Za-z_][\w.]*)\s*=\s*[A-Za-z_][\w.]*\s*\(",  # alias = f(
    re.M,
)
CALL_RE = re.compile(r"(?<![\w.:])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(")
REQUIRE_RE = re.compile(r"require\s*\(?\s*['\"]([^'\"]+)['\"]")

LUA_KEYWORDS = {
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function", "if",
    "in", "local", "nil", "not", "or", "repeat", "return", "then", "true", "until", "while",
    "print", "type", "pairs", "ipairs", "next", "tostring", "tonumber", "error", "assert",
    "pcall", "xpcall", "select", "unpack", "setmetatable", "getmetatable", "rawget",
    "rawset", "table", "string", "math", "os", "io", "coroutine", "require", "collectgarbage",
    "dofile", "loadfile", "loadstring", "module", "rawequal", "unpack",
}


def scan(root):
    files = 0
    defined = set()
    calls = collections.Counter()
    requires = collections.Counter()
    dirs = collections.Counter()
    dir_bytes = collections.Counter()
    logic_hits = collections.Counter()   # scripts that contain real control flow
    total_bytes = 0
    for dp, dn, fn in os.walk(root):
        rel = os.path.relpath(dp, root)
        for f in fn:
            if not f.lower().endswith(".lua"):
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    t = fh.read()
                size = os.path.getsize(p)
            except OSError:
                continue
            files += 1
            total_bytes += size
            dirs[rel] += 1
            dir_bytes[rel] += size
            if re.search(r"\b(if|for|while|repeat)\b", t):
                logic_hits[rel] += 1
            for m in DEF_RE.finditer(t):
                defined.add(m.group(1) or m.group(2) or m.group(3))
            for m in CALL_RE.finditer(t):
                calls[m.group(1)] += 1
            for m in REQUIRE_RE.finditer(t):
                requires[m.group(1)] += 1
    return files, total_bytes, defined, calls, requires, dirs, dir_bytes, logic_hits


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_game = r"D:\Games\W6W-05"
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=default_game)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(here)), "docs", "recon"))
    args = ap.parse_args()

    root = os.path.join(args.game, "data")
    exe_root = os.path.join(args.game, "data_jp")
    out = {"roots": []}
    for label, base in (("data", root), ("data_jp", exe_root)):
        if not os.path.isdir(base):
            continue
        files, total, defined, calls, requires, dirs, dir_bytes, logic = scan(base)
        undefined = {}
        for name, n in calls.items():
            if name in defined or name in LUA_KEYWORDS:
                continue
            head = name.split(".")[0]
            if head in defined or head in LUA_KEYWORDS:
                continue
            undefined[name] = n
        # native-looking: undefined, capitalised or prefix-built, not an all-caps car name
        native = {k: v for k, v in undefined.items()
                  if not (k.isupper() and len(k) <= 12) and re.search(r"[a-z]", k)}
        out["roots"].append({
            "root": base,
            "files": files,
            "bytes": total,
            "defined": len(defined),
            "calls": len(calls),
            "undefined": len(undefined),
            "native_candidates": len(native),
            "native_top": sorted(native.items(), key=lambda kv: -kv[1])[:200],
            "undefined_top": sorted(undefined.items(), key=lambda kv: -kv[1])[:200],
            "requires_top": requires.most_common(50),
            "dirs": [{"dir": d, "files": n, "bytes": dir_bytes[d], "with_logic": logic[d]}
                     for d, n in dirs.most_common(80)],
            "defined_names": sorted(defined)[:4000],
        })
        print("==", label, base)
        print("   files", files, "bytes", total, "defined", len(defined), "native candidates", len(native))
        print("   top native:", ", ".join("%s(%d)" % kv for kv in sorted(native.items(), key=lambda kv: -kv[1])[:12]))
        print("   top dirs  :", ", ".join("%s:%d" % (d, n) for d, n in dirs.most_common(8)))

    os.makedirs(args.out, exist_ok=True)
    dst = os.path.join(args.out, "lua.json")
    with open(dst, "w", encoding="utf8") as f:
        json.dump(out, f, indent=1)
    print("wrote", dst)


if __name__ == "__main__":
    sys.exit(main())
