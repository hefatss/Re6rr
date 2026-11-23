"""List small leaf functions - the starting point for the lifter spike.

    python tools/x64/simple_funcs.py [--max-size 64] [--limit 40] [--out FILE]

A function is listed when it is no larger than --max-size, contains no direct
`call`, and its only branch targets are inside its own body. Those are the
cheapest bodies to lift and to differential-test against Unicorn.
"""

import argparse
import bisect
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
from pe_report import PE  # noqa: E402

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET
except ImportError:  # pragma: no cover
    raise SystemExit("capstone missing: python -m pip install capstone")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--max-size", type=int, default=64)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--require-jcc", action="store_true", help="only functions with an internal conditional branch")
    ap.add_argument("--require-ret", action="store_true", help="only functions that end in ret")
    ap.add_argument("--out")
    args = ap.parse_args()

    pe = PE(args.exe)
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

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True

    rows = []
    for start, end in funcs:
        n = end - start
        if n > args.max_size or start < code_base or end > code_base + len(code):
            continue
        body = code[start - code_base:end - code_base]
        insns = [i for i in md.disasm(body, start) if i.id]
        if not insns or any(i.group(CS_GRP_CALL) for i in insns):
            continue
        bad = False
        for i in insns:
            if i.group(CS_GRP_JUMP) or i.group(CS_GRP_RET):
                imm = i.operands[0].imm if i.operands and i.operands[0].type == 2 else None
                if imm is not None and not (start <= imm <= end):
                    bad = True
                    break
        if bad:
            continue
        if args.require_jcc and not any(i.group(CS_GRP_JUMP) and i.mnemonic != "jmp" for i in insns):
            continue
        if args.require_ret and insns[-1].mnemonic not in ("ret", "retn"):
            continue
        mnem = collections.Counter(i.mnemonic for i in insns)
        rows.append((n, len(insns), start, end, insns, mnem))
        if len(rows) >= args.limit * 4:
            break

    lines = ["%d leaf functions <= %d bytes" % (len(rows), args.max_size), "",
             "| function | bytes | insns | mnemonics |", "|---|---|---|---|"]
    for n, k, start, end, insns, mnem in rows[:args.limit]:
        lines.append("| `f_%x` | %d | %d | %s |" % (
            start, n, k, " ".join("%s:%d" % (m, c) for m, c in mnem.most_common(8))))
    text_out = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf8") as f:
            f.write(text_out + "\n")
    print(text_out)
    print("\nwrote:", args.out or "(stdout)")


if __name__ == "__main__":
    sys.exit(main())
