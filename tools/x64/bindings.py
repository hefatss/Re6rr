"""Merge code xrefs and name tables into one name -> implementation map.

    python tools/x64/bindings.py [--out docs/recon/BINDINGS.md]

Two ways a Lua-visible name reaches native code:

  * direct: a function loads the name with a RIP-relative operand
    (typically `lea r8, [rip+...] ; "GetAura_BG_Alpha"`) — from xrefs.json
  * table: the name is one entry of a pointer table and the table is loaded by
    a function — from name_tables.json

All 219 names from the Lua API list are covered by one of the two.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "recon", "BINDINGS.md"))
    args = ap.parse_args()

    recon = os.path.join(ROOT, "docs", "recon")
    xrefs = json.load(open(os.path.join(recon, "xrefs.json"), encoding="utf8"))["hits"]
    tabs = json.load(open(os.path.join(recon, "name_tables.json"), encoding="utf8"))
    names = [l.strip() for l in open(os.path.join(recon, "lua_api_names.txt"), encoding="utf8") if l.strip()]

    where = {}
    for name, funcs in xrefs.items():
        where.setdefault(name, {"via": "code", "funcs": sorted(funcs), "tables": []})
    for group in ("reg", "strings"):
        for t in tabs[group]:
            entries = t.get("entries") or [[n, None] for n in t["names"]]
            for name, fn in entries:
                if name not in names:
                    continue
                rec = where.setdefault(name, {"via": "table", "funcs": [], "tables": []})
                rec["tables"].append({"rva": t["rva"], "kind": t["kind"],
                                      "users": t.get("users", [])})
                if fn is not None:
                    rec["funcs"].append(fn)
                    rec["via"] = "luaL_Reg"

    # Fallback for names in tables where a hole (zero qword) broke the run scan:
    # search .rdata/.data for a qword pointing at the name string itself.
    unresolved = [n for n in names if n not in where]
    if unresolved:
        from pe_report import PE
        pe = PE(args.exe)
        refs = {int(k, 16): v for k, v in json.load(
            open(os.path.join(recon, "refs.json"), encoding="utf8")).items()}
        targets = {}
        for name in unresolved:
            needle = name.encode("ascii") + b"\0"
            for sec in pe.sections:
                if sec["name"] not in (".rdata", ".data"):
                    continue
                o = sec["raw_ptr"]
                data = pe.raw[o:o + sec["raw_size"]]
                pos = data.find(needle)
                if pos >= 0:
                    targets[name] = pe.image_base + sec["vaddr"] + pos
                    break
        for sec in pe.sections:
            if sec["name"] not in (".rdata", ".data"):
                continue
            o = sec["raw_ptr"]
            data = pe.raw[o:o + sec["raw_size"]]
            for i in range(len(data) // 8):
                val = struct.unpack_from("<Q", data, 8 * i)[0]
                for name, target in list(targets.items()):
                    if val != target:
                        continue
                    ptr_rva = sec["vaddr"] + 8 * i
                    users = sorted(set(u for d in range(0, 64, 8)
                                       for u in refs.get(ptr_rva - d, [])))
                    where[name] = {"via": "pointer", "funcs": [], "tables": [
                        {"rva": ptr_rva, "kind": "pointer", "users": users}]}
                    del targets[name]

    direct = [n for n in names if where.get(n, {}).get("via") == "code"]
    table = [n for n in names if n not in direct]
    missing = [n for n in names if n not in where]

    lines = ["# Lua bindings: name → native implementation", "",
             "%d names from `LUA_API.md`; %d resolved directly in code, %d through name tables, "
             "%d unresolved." % (len(names), len(direct), len(table), len(missing)), "",
             "A direct hit means some function has the name as a RIP-relative operand, e.g. "
             "`lea r8, [rip+...] ; \"GetAura_BG_Alpha\"`. A table hit means the name lives in a "
             "pointer table loaded by the implementation. Both are addresses, not symbols: the "
             "binary has no COFF symbol table.", "",
             "## Direct hits", "",
             "| name | function |", "|---|---|"]
    for n in sorted(direct):
        lines.append("| `%s` | %s |" % (n, ", ".join("`f_%x`" % f for f in where[n]["funcs"])))

    lines += ["", "## Table-loaded names", "",
              "| name | table | loaded by |", "|---|---|---|"]
    for n in sorted(table):
        rec = where.get(n)
        if not rec:
            continue
        t = rec["tables"][0] if rec["tables"] else {"rva": 0, "users": []}
        lines.append("| `%s` | `0x%x` | %s |" % (
            n, t["rva"], ", ".join("`f_%x`" % u for u in t["users"][:4]) if t["users"] else "-"))

    if missing:
        lines += ["", "## Unresolved", ""] + ["- `%s`" % n for n in missing]

    with open(args.out, "w", encoding="utf8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(recon, "bindings.json"), "w", encoding="utf8") as f:
        json.dump({n: where.get(n, {}) for n in names}, f, indent=1)
    print("direct:", len(direct), "table:", len(table), "unresolved:", len(missing))
    print("wrote:", args.out)


if __name__ == "__main__":
    sys.exit(main())
