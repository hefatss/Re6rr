"""Find which function refers to which string, without a full disassembler DB.

    python tools/x64/string_xref.py [--names FILE] [--out docs/recon/xrefs.json]

The PE has no symbols, but it does keep every readable string and a complete
.pdata function table. A linear sweep of .text finds RIP-relative operands
(`lea rax, [rip+x]`, `mov rax, [rip+x]`) and maps each target that lands on a
string to the function containing the instruction.

With --names (one identifier per line, e.g. the Lua API list) only references to
those strings are reported; otherwise every referenced string is summarised.

Needs `capstone` (pip install capstone).
"""

import argparse
import bisect
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recon"))
from pe_report import PE  # noqa: E402

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from capstone.x86 import X86_OP_MEM, X86_REG_RIP
except ImportError:  # pragma: no cover
    raise SystemExit("capstone missing: python -m pip install capstone")

STRING_RE = re.compile(rb"[ -~]{4,200}")


def collect_strings(pe):
    out = {}
    for sec in pe.sections:
        if sec["name"] in (".pdata", ".reloc", ".rsrc", ".tls"):
            continue
        base = sec["raw_ptr"]
        data = pe.raw[base:base + sec["raw_size"]]
        for m in STRING_RE.finditer(data):
            rva = sec["vaddr"] + m.start()
            out[rva] = m.group(0).decode("latin1")
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--names", help="file with one name per line")
    ap.add_argument("--out", default=os.path.join(root, "docs", "recon", "xrefs.json"))
    ap.add_argument("--all", action="store_true", help="report every referenced string, not only --names")
    args = ap.parse_args()

    pe = PE(args.exe)
    strings = collect_strings(pe)

    # function table from .pdata
    rva, size = pe.dirs[3]
    off = pe.off(rva)
    funcs = []
    for i in range(size // 12):
        begin, end, _unwind = __import__("struct").unpack_from("<III", pe.raw, off + 12 * i)
        if begin and end > begin:
            funcs.append((begin, end))
    funcs.sort()
    starts = [f[0] for f in funcs]

    def owner(rva_insn):
        i = bisect.bisect_right(starts, rva_insn) - 1
        if i >= 0 and funcs[i][0] <= rva_insn < funcs[i][1]:
            return funcs[i][0]
        return None

    text = next(s for s in pe.sections if s["name"] == ".text")
    code = pe.raw[text["raw_ptr"]:text["raw_ptr"] + text["raw_size"]]
    base_rva = text["vaddr"]

    wanted = None
    if args.names:
        names = [l.strip() for l in open(args.names, encoding="utf8") if l.strip()]
        wanted = set(names)

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    hits = collections.defaultdict(set)
    all_refs = collections.defaultdict(set)
    scanned = 0
    refs = 0
    for insn in md.disasm(code, base_rva):
        if insn.id == 0:  # skipped data byte
            continue
        scanned += 1
        for op in insn.operands:
            if op.type != X86_OP_MEM or op.mem.base != X86_REG_RIP:
                continue
            target = insn.address + insn.size + op.mem.disp
            fn = owner(insn.address)
            if fn is not None:
                all_refs[target].add(fn)
            s = strings.get(target)
            if s is None:
                continue
            refs += 1
            if wanted is not None and s not in wanted:
                continue
            if fn is None:
                continue
            hits[s].add(fn)

    refs_out = os.path.join(os.path.dirname(args.out), "refs.json")
    with open(refs_out, "w", encoding="utf8") as f:
        json.dump({hex(k): sorted(v) for k, v in all_refs.items()}, f)
    print("data refs     :", len(all_refs), "->", refs_out)


    rep = {
        "exe": os.path.abspath(args.exe),
        "instructions": scanned,
        "string_refs": refs,
        "strings": len(strings),
        "names_requested": len(wanted) if wanted else None,
        "names_found": len(hits),
        "hits": {k: sorted(v) for k, v in sorted(hits.items())},
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf8") as f:
        json.dump(rep, f, indent=1)

    print("instructions  :", scanned)
    print("string refs   :", refs, "distinct strings", len(strings))
    if wanted:
        print("names found   :", len(hits), "of", len(wanted))
        missing = sorted(wanted - set(hits))
        if missing:
            print("missing       :", ", ".join(missing[:20]), "..." if len(missing) > 20 else "")
        for k in list(sorted(hits))[:10]:
            print("  %-32s -> %s" % (k, ", ".join("f_%x" % a for a in sorted(hits[k])[:4])))
    print("wrote         :", args.out)


if __name__ == "__main__":
    sys.exit(main())
