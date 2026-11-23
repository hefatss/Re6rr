"""Find tables of pointers to strings - the likely Lua binding/registration tables.

    python tools/x64/name_table.py [--refs docs/recon/refs.json] [--out docs/recon/NAME_TABLE.md]

`string_xref.py` only sees names a function loads directly. Engines usually keep
`{ "Name", function }` records in a data table and hand the whole table to the
script layer, so the names never appear as code operands.

Two scans run over `.rdata`/`.data`:

  * string runs - consecutive qwords that all point at printable strings
  * `luaL_Reg` runs - 16-byte records whose first qword points at a printable
    string and whose second qword points into `.text` (the lua_CFunction)

The `luaL_Reg` scan is the important one: it recovers name -> implementation for
every binding in the table without any per-function analysis.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
from pe_report import PE  # noqa: E402
from string_xref import collect_strings  # noqa: E402

STRIDES = (8, 16, 24, 32, 40, 48, 56, 64)


def qwords(pe, sec):
    base = sec["raw_ptr"]
    data = pe.raw[base:base + sec["raw_size"]]
    n = len(data) // 8
    return [struct.unpack_from("<Q", data, 8 * i)[0] for i in range(n)]


def find_runs(pe, strings):
    runs = []
    for sec in pe.sections:
        if sec["name"] not in (".rdata", ".data"):
            continue
        vals = qwords(pe, sec)
        vaddr = sec["vaddr"]
        n = len(vals)
        ptr = [v - pe.image_base if v - pe.image_base in strings else None for v in vals]
        i = 0
        while i < n:
            if ptr[i] is None:
                i += 1
                continue
            best = None
            for stride in STRIDES:
                j = i
                count = 0
                while j < n and ptr[j] is not None:
                    count += 1
                    j += stride // 8
                if count >= 4 and (best is None or count > best[1]):
                    best = (stride, count, j)
            if best is None:
                i += 1
                continue
            stride, count, j = best
            step = stride // 8
            runs.append({
                "kind": "strings",
                "rva": vaddr + 8 * i,
                "size": 8 * (j - i),
                "stride": stride,
                "count": count,
                "names": [strings[ptr[k]] for k in range(i, j, step)],
            })
            i = j
    runs.sort(key=lambda r: -r["count"])
    return runs


def find_reg_tables(pe, strings, text_lo, text_hi):
    """Runs of {char *name; void *fn} records, the luaL_Reg layout."""
    runs = []
    for sec in pe.sections:
        if sec["name"] not in (".rdata", ".data"):
            continue
        vals = qwords(pe, sec)
        vaddr = sec["vaddr"]
        n = len(vals) // 2
        rec = []
        for i in range(n):
            a = vals[2 * i] - pe.image_base
            b = vals[2 * i + 1] - pe.image_base
            name = strings.get(a) if a in strings else None
            ok = name is not None and name.strip() and text_lo <= b < text_hi
            rec.append((name, b) if ok else None)
        i = 0
        while i < n:
            if rec[i] is None:
                i += 1
                continue
            j = i
            while j < n and rec[j] is not None:
                j += 1
            if j - i >= 3:
                runs.append({
                    "kind": "luaL_Reg",
                    "rva": vaddr + 16 * i,
                    "size": 16 * (j - i),
                    "stride": 16,
                    "count": j - i,
                    "entries": [[rec[k][0], rec[k][1]] for k in range(i, j)],
                    "names": [rec[k][0] for k in range(i, min(j, i + 8))],
                })
            i = j
    runs.sort(key=lambda r: -r["count"])
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--refs", default=os.path.join(ROOT, "docs", "recon", "refs.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "recon", "NAME_TABLE.md"))
    args = ap.parse_args()

    pe = PE(args.exe)
    strings = collect_strings(pe)
    text = next(s for s in pe.sections if s["name"] == ".text")
    text_lo = text["vaddr"]
    text_hi = text_lo + text["raw_size"]

    runs = find_runs(pe, strings)
    regs = find_reg_tables(pe, strings, text_lo, text_hi)

    refs = {}
    if os.path.exists(args.refs):
        refs = {int(k, 16): v for k, v in json.load(open(args.refs, encoding="utf8")).items()}

    def users_of(rva, size):
        out = set()
        for delta in range(0, min(size, 128), 8):
            out |= set(refs.get(rva + delta, []))
        return sorted(out)

    lines = ["# Pointer tables that name engine functions", "",
             "`luaL_Reg` runs are `{ char *name; void *fn }` records whose name is printable "
             "and whose fn lands in `.text`. Those give name -> implementation directly.", "",
             "## luaL_Reg-style tables", "",
             "| table | entries | first names | loaded by |", "|---|---|---|---|"]
    reg_rep = []
    for r in regs:
        u = users_of(r["rva"], r["size"])
        r["users"] = u
        reg_rep.append(r)
        lines.append("| `0x%x` | %d | %s | %s |" % (
            r["rva"], r["count"], ", ".join(r["names"][:5]),
            ", ".join("`f_%x`" % x for x in u[:3]) if u else "-"))

    lines += ["", "## Plain string-pointer runs", "",
              "| table | stride | entries | first names | loaded by |", "|---|---|---|---|---|"]
    str_rep = []
    for r in runs:
        u = users_of(r["rva"], r["size"])
        r["users"] = u
        str_rep.append(r)
        lines.append("| `0x%x` | %d | %d | %s | %s |" % (
            r["rva"], r["stride"], r["count"], ", ".join(r["names"][:5]),
            ", ".join("`f_%x`" % x for x in u[:3]) if u else "-"))

    with open(args.out, "w", encoding="utf8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(os.path.dirname(args.out), "name_tables.json"), "w", encoding="utf8") as f:
        json.dump({"reg": reg_rep, "strings": str_rep}, f, indent=1)

    print("luaL_Reg tables :", len(regs))
    for r in regs[:10]:
        print("  %08x  %3d entries  %s" % (r["rva"], r["count"], ", ".join(r["names"][:4])))
    print("string runs     :", len(runs))
    for r in runs[:6]:
        print("  %08x  stride %2d count %3d  %s" % (r["rva"], r["stride"], r["count"],
                                                    ", ".join(r["names"][:4])))
    print("wrote           :", args.out)


if __name__ == "__main__":
    sys.exit(main())
