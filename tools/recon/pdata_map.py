"""List every function the PE declares in .pdata, with its unwind record.

    python tools/recon/pdata_map.py [--exe PATH] [--out docs/recon/pdata.json]

The exception directory is the port's function inventory: one RUNTIME_FUNCTION
per function, exact start/end RVAs, plus the UNWIND_INFO that says how big the
stack frame is and which registers are saved. That is what an x86-64 recompiler
needs before it decodes a single instruction.

Also reports how many functions are leaf (no unwind codes), chained, or share an
unwind record, and the histogram of function sizes.
"""

import argparse
import json
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe_report import PE  # noqa: E402

UNW_FLAG_EHANDLER = 0x1
UNW_FLAG_UHANDLER = 0x2
UNW_FLAG_CHAININFO = 0x4


def read_unwind(pe, rva):
    o = pe.off(rva)
    if o is None:
        return None
    d = pe.raw
    version_flags = d[o]
    prolog = d[o + 1]
    codes = d[o + 2]
    frame = d[o + 3]
    info = {
        "version": version_flags & 0x7,
        "flags": version_flags >> 3,
        "prolog": prolog,
        "codes": codes,
        "frame_reg": frame & 0xF,
        "frame_off": (frame >> 4) * 16,
    }
    if info["flags"] & UNW_FLAG_CHAININFO:
        slot = o + 4 + 2 * codes
        if slot % 2:
            slot += 1
        begin, end, chain = struct.unpack_from("<III", d, slot)
        info["chain"] = {"begin": hex(begin), "end": hex(end), "unwind": hex(chain)}
    return info


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(here)), "docs", "recon", "pdata.json"))
    args = ap.parse_args()

    pe = PE(args.exe)
    rva, size = pe.dirs[3]
    o = pe.off(rva)
    if o is None:
        raise SystemExit("no .pdata")
    funcs = []
    for i in range(size // 12):
        begin, end, unwind = struct.unpack_from("<III", pe.raw, o + 12 * i)
        if begin == 0 or end <= begin:
            continue
        info = read_unwind(pe, unwind) or {}
        funcs.append({
            "begin": begin,
            "end": end,
            "size": end - begin,
            "section": pe.section_of(begin),
            "unwind_rva": unwind,
            "leaf": bool(info) and info.get("codes", 0) == 0 and not (info.get("flags", 0) & UNW_FLAG_CHAININFO),
            "flags": info.get("flags", 0),
            "chain": info.get("chain"),
        })
    funcs.sort(key=lambda f: f["begin"])

    sizes = [f["size"] for f in funcs]
    hist = collections.Counter()
    for s in sizes:
        if s < 16:
            hist["<16"] += 1
        elif s < 32:
            hist["16-31"] += 1
        elif s < 64:
            hist["32-63"] += 1
        elif s < 128:
            hist["64-127"] += 1
        elif s < 256:
            hist["128-255"] += 1
        elif s < 1024:
            hist["256-1023"] += 1
        else:
            hist[">=1024"] += 1

    rep = {
        "exe": os.path.abspath(args.exe),
        "functions": len(funcs),
        "code_bytes": sum(sizes),
        "text_bytes": next((s["raw_size"] for s in pe.sections if s["name"] == ".text"), None),
        "leaf": sum(1 for f in funcs if f["leaf"]),
        "chained": sum(1 for f in funcs if f["chain"]),
        "with_eh": sum(1 for f in funcs if f["flags"] & UNW_FLAG_EHANDLER),
        "sections": dict(collections.Counter(f["section"] for f in funcs)),
        "size_histogram": dict(hist),
        "min": min(sizes) if sizes else None,
        "max": max(sizes) if sizes else None,
        "median": sorted(sizes)[len(sizes) // 2] if sizes else None,
        "largest": sorted(funcs, key=lambda f: -f["size"])[:20],
        "list": [{"rva": f["begin"], "end": f["end"], "size": f["size"], "leaf": f["leaf"]} for f in funcs],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf8") as f:
        json.dump(rep, f, indent=1)

    print("functions     :", rep["functions"])
    print("code bytes    :", rep["code_bytes"], "of .text", rep["text_bytes"])
    print("leaf / chained:", rep["leaf"], "/", rep["chained"])
    print("size min/med/max:", rep["min"], rep["median"], rep["max"])
    print("histogram     :", dict(hist))
    print("sections      :", rep["sections"])
    print("largest       :", ", ".join("%x(%d)" % (f["begin"], f["size"]) for f in rep["largest"][:8]))
    print("wrote         :", args.out)


if __name__ == "__main__":
    sys.exit(main())
