"""Disassemble one function and annotate its operands.

    python tools/x64/func_disasm.py f_152090 [f_c9a40 ...] [--exe PATH]
    python tools/x64/func_disasm.py --rva 0x152090

Writes docs/recon/disasm/<name>.asm and prints the same text.

Annotations come from data already recovered:
  * RIP-relative operands that land on a printable string are shown as the text
  * direct call/jump targets that are a .pdata function start become `f_<rva>`
    plus any engine name known to live in that function
  * operands that land in the import address table become `dll!Function`
"""

import argparse
import bisect
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
from pe_report import PE, u32, u64  # noqa: E402
from string_xref import collect_strings  # noqa: E402

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_GRP_CALL, CS_GRP_JUMP
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
except ImportError:  # pragma: no cover
    raise SystemExit("capstone missing: python -m pip install capstone")


def iat_map(pe):
    """rva of every import slot -> 'dll!Name'."""
    out = {}
    rva, size = pe.dirs[1]
    if not rva:
        return out
    o = pe.off(rva)
    idx = 0
    while True:
        desc = o + 20 * idx
        ilt = u32(pe.raw, desc)
        name_rva = u32(pe.raw, desc + 12)
        iat = u32(pe.raw, desc + 16)
        if not (ilt or name_rva or iat):
            break
        dll = pe.cstr(name_rva) or "?"
        tbl = pe.off(ilt or iat)
        if tbl is not None:
            j = 0
            while True:
                val = u64(pe.raw, tbl + 8 * j)
                if not val:
                    break
                if val >> 63:
                    fn = "#%d" % (val & 0xFFFF)
                else:
                    fn = pe.cstr((val & 0x7FFFFFFF) + 2) or "?"
                out[iat + 8 * j] = "%s!%s" % (dll, fn)
                j += 1
        idx += 1
    return out


def load_names():
    path = os.path.join(ROOT, "docs", "recon", "xrefs.json")
    if not os.path.exists(path):
        return {}
    hits = json.load(open(path, encoding="utf8"))["hits"]
    by_func = {}
    for name, funcs in hits.items():
        for f in funcs:
            by_func.setdefault(f, []).append(name)
    return by_func


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("funcs", nargs="*", help="function names like f_152090")
    ap.add_argument("--rva", action="append", default=[], help="hex RVA")
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "docs", "recon", "disasm"))
    ap.add_argument("--raw", action="store_true", help="no annotations")
    ap.add_argument("--max", type=int, default=4000, help="instruction cap per function")
    args = ap.parse_args()

    targets = []
    for f in args.funcs:
        m = re.fullmatch(r"f_([0-9a-fA-F]+)", f)
        if not m:
            raise SystemExit("bad function name %r (expected f_<hex rva>)" % f)
        targets.append(int(m.group(1), 16))
    targets += [int(r, 16) for r in args.rva]
    if not targets:
        raise SystemExit("no function given")

    pe = PE(args.exe)
    strings = {} if args.raw else collect_strings(pe)
    iat = {} if args.raw else iat_map(pe)
    names = {} if args.raw else load_names()

    rva, size = pe.dirs[3]
    off = pe.off(rva)
    funcs = []
    for i in range(size // 12):
        begin, end, _ = struct.unpack_from("<III", pe.raw, off + 12 * i)
        if begin and end > begin:
            funcs.append((begin, end))
    funcs.sort()
    starts = [f[0] for f in funcs]
    text = next(s for s in pe.sections if s["name"] == ".text")
    code = pe.raw[text["raw_ptr"]:text["raw_ptr"] + text["raw_size"]]
    code_base = text["vaddr"]
    code_end = code_base + len(code)

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True

    os.makedirs(args.out_dir, exist_ok=True)
    for start in targets:
        i = bisect.bisect_right(starts, start) - 1
        if i < 0 or funcs[i][0] != start:
            print("f_%x: not a .pdata function start" % start)
            continue
        end = funcs[i][1]
        if start < code_base or end > code_end:
            print("f_%x: outside .text" % start)
            continue
        body = code[start - code_base:end - code_base]
        lines = ["f_%x  (%d bytes)" % (start, end - start)]
        if names.get(start):
            lines.append("names: " + ", ".join(sorted(names[start])))
        lines.append("")
        count = 0
        for insn in md.disasm(body, start):
            if insn.id == 0:
                continue
            count += 1
            if count > args.max:
                lines.append("... truncated")
                break
            note = ""
            for op in insn.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    tgt = insn.address + insn.size + op.mem.disp
                    if tgt in strings:
                        note = '  ; "%s"' % strings[tgt].strip()
                        break
                    if tgt in iat:
                        note = "  ; " + iat[tgt]
                        break
                    note = "  ; data_%x" % tgt
                    break
                if op.type == X86_OP_IMM and (insn.group(CS_GRP_CALL) or insn.group(CS_GRP_JUMP)):
                    tgt = op.imm
                    if tgt in starts:
                        extra = names.get(tgt)
                        note = "  ; f_%x" % tgt + (" [" + ",".join(sorted(extra)[:2]) + "]" if extra else "")
            lines.append("%08x  %-28s %-8s %s%s" % (
                insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str, note))
        path = os.path.join(args.out_dir, "f_%x.asm" % start)
        with open(path, "w", encoding="utf8") as f:
            f.write("\n".join(lines) + "\n")
        print("\n".join(lines))
        print("\nwrote:", path)


if __name__ == "__main__":
    sys.exit(main())
