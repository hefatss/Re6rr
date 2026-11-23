"""Emit readable C for IR lifted from a function.

    python tools/x64/emit_c.py f_8555 f_68e0 --out docs/recon/c

The output is a mechanical transcription of the same IR that interp.py executes
and difftest.py checks against Unicorn. It is intentionally explicit about
registers, flags and memory; optimisation into idiomatic C comes later, once the
lift is validated on a larger set of functions.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
sys.path.insert(0, HERE)

from pe_report import PE  # noqa: E402
from x86model import REGS, canon  # noqa: E402
from lift import lift_function, Unsupported  # noqa: E402
from interp import size_of  # noqa: E402

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
except ImportError:  # pragma: no cover
    raise SystemExit("capstone missing: python -m pip install capstone")

MASK = {8: "0xff", 16: "0xffff", 32: "0xffffffffu", 64: "UINT64_MAX"}
CAST = {8: "uint8_t", 16: "uint16_t", 32: "uint32_t", 64: "uint64_t"}

PREAMBLE = r"""/* Machine-transcribed from wmn6r.exe. Registers/flags are explicit; run
 * tools/x64/difftest.py before trusting any of this as source. */
#include <stdint.h>
#include <string.h>

enum { RAX=0, RCX=1, RDX=2, RBX=3, RSP=4, RBP=5, RSI=6, RDI=7,
       R8=8, R9=9, R10=10, R11=11, R12=12, R13=13, R14=14, R15=15 };
typedef struct { uint64_t r[16]; uint64_t zf, sf, cf, of; uint8_t *mem; } Cpu;

static inline uint64_t rd(Cpu *c, uint64_t a, int bits) {
    uint64_t v = 0;
    memcpy(&v, c->mem + a, bits / 8);
    return bits == 64 ? v : v & ((1ULL << bits) - 1);
}
static inline void wr(Cpu *c, uint64_t a, int bits, uint64_t v) {
    memcpy(c->mem + a, &v, bits / 8);
}
static inline void set_logic(Cpu *c, uint64_t v, int bits) {
    uint64_t m = bits == 64 ? UINT64_MAX : ((1ULL << bits) - 1);
    v &= m;
    c->zf = v == 0; c->sf = (v >> (bits - 1)) & 1; c->cf = c->of = 0;
}
static inline void set_add(Cpu *c, uint64_t a, uint64_t b, int bits, int sub) {
    uint64_t m = bits == 64 ? UINT64_MAX : ((1ULL << bits) - 1);
    uint64_t res = sub ? (a - b) & m : (a + b) & m;
    c->cf = sub ? (a & m) < (b & m) : (a & m) + (b & m) > m;
    c->of = sub ? ((a ^ b) & (a ^ res) & (1ULL << (bits - 1))) != 0
                : ((~(a ^ b) & (a ^ res) & (1ULL << (bits - 1)))) != 0;
    c->zf = res == 0; c->sf = (res >> (bits - 1)) & 1;
}
static inline int cc_true(Cpu *c, const char *cc) {
    if (!strcmp(cc,"e")) return c->zf;
    if (!strcmp(cc,"ne")) return !c->zf;
    if (!strcmp(cc,"l")) return c->sf != c->of;
    if (!strcmp(cc,"ge")) return c->sf == c->of;
    if (!strcmp(cc,"le")) return c->zf || c->sf != c->of;
    if (!strcmp(cc,"g")) return !c->zf && c->sf == c->of;
    if (!strcmp(cc,"b")) return c->cf;
    if (!strcmp(cc,"ae")) return !c->cf;
    if (!strcmp(cc,"be")) return c->cf || c->zf;
    if (!strcmp(cc,"a")) return !c->cf && !c->zf;
    if (!strcmp(cc,"s")) return c->sf;
    if (!strcmp(cc,"ns")) return !c->sf;
    return 0; /* remaining conditions: fill in when needed */
}
"""


def reg_id(name):
    parent = canon(name)[0]
    return REGS.index(parent)


def reg_read(op, bits):
    name = op[1]
    parent, shift, rbits = canon(name)
    r = "c->r[%s]" % parent.upper() if parent.upper() in (
        "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI") else "c->r[%s]" % parent.upper()
    if rbits == bits:
        return r if shift == 0 else "((%s >> %d) & %s)" % (r, shift, MASK[rbits])
    return "((%s)(%s >> %d))" % (CAST[bits], r, shift)


def reg_write(op, value, bits):
    name = op[1]
    parent, shift, rbits = canon(name)
    r = "c->r[%s]" % parent.upper()
    if shift == 0 and bits == rbits:
        return "%s = (%s) & %s;" % (r, value, MASK[bits])
    if bits == 32 and rbits == 64 and shift == 0:
        return "%s = (%s & ~0xffffffffULL) | (uint32_t)(%s);" % (r, r, value)
    return "%s = (%s & ~(%sULL << %d)) | ((%s & %s) << %d);" % (
        r, r, MASK[bits], shift, value, MASK[bits], shift)


def addr(op):
    _, base, index, scale, disp = op[:5]
    parts = []
    if isinstance(base, int):
        parts.append("0x%xULL" % base)
    elif base is not None:
        parts.append("c->r[%s]" % base.upper())
    if index is not None:
        parts.append("c->r[%s] * %d" % (index.upper(), scale or 1))
    if disp:
        parts.append(("0x%x" % disp) if disp > 0 else "-(0x%x)" % -disp)
    return " + ".join(parts) if parts else "0"


def val(op, bits=64):
    if op[0] == "imm":
        return "0x%xULL" % (op[1] & 0xFFFFFFFFFFFFFFFF)
    if op[0] == "reg":
        return reg_read(op, bits)
    if op[0] == "mem":
        return "rd(c, %s, %d)" % (addr(op), op[5])
    if op[0] == "ea":
        return addr(("mem",) + op[1:] + (64,))
    raise AssertionError(op)


def put(op, expr, bits):
    if op[0] == "reg":
        return reg_write(op, expr, bits)
    if op[0] == "mem":
        return "wr(c, %s, %d, %s);" % (addr(op), op[5], expr)
    raise AssertionError(op)


def emit(items, start, end):
    lines = []
    targets = set()
    for it in items:
        if it["op"] in ("jmp", "jcc"):
            targets.add(it["args"][-1])
    emitted_label = set()
    for it in items:
        op, args = it["op"], it["args"]
        if it["a"] in targets and it["a"] not in emitted_label:
            lines.append("L_%x:" % it["a"])
            emitted_label.add(it["a"])
        lines.append("    /* %08x */" % it["a"])
        if op == "mov":
            bits = size_of(args[0])
            lines.append("    " + put(args[0], val(args[1], bits), bits))
        elif op == "movzx":
            bits = size_of(args[0])
            lines.append("    " + put(args[0], val(args[1], size_of(args[1])), bits))
        elif op == "movsx":
            bits = size_of(args[0])
            sb = size_of(args[1])
            lines.append("    " + put(args[0], "(int%d_t)%s" % (sb, val(args[1], sb)), bits))
        elif op == "lea":
            bits = size_of(args[0])
            lines.append("    " + put(args[0], val(("ea",) + tuple(args[1])), bits))
        elif op == "bin":
            name, dst, a, b = args
            bits = size_of(dst)
            av, bv = val(a, bits), val(b, bits)
            sym = {"add": "+", "sub": "-", "and": "&", "or": "|", "xor": "^",
                   "shl": "<<", "shr": ">>", "sar": ">>", "imul": "*"}.get(name, "+")
            if name in ("add", "sub", "adc", "sbb"):
                lines.append("    set_add(c, %s, %s, %d, %d);" % (av, bv, bits, name in ("sub", "sbb")))
            elif name in ("and", "or", "xor", "imul"):
                lines.append("    set_logic(c, (%s) %s (%s), %d);" % (av, sym, bv, bits))
            lines.append("    " + put(dst, "(%s) %s (%s)" % (av, sym, bv), bits))
        elif op == "un":
            name, dst, a = args
            bits = size_of(dst)
            av = val(a, bits)
            sym = {"neg": "-", "not": "~", "inc": "+ 1", "dec": "- 1"}.get(name, "+ 0")
            lines.append("    " + put(dst, "%s %s" % (av, sym), bits))
        elif op == "cmp":
            bits = size_of(args[0])
            lines.append("    set_add(c, %s, %s, %d, 1);" % (
                val(args[0], bits), val(args[1], bits), bits))
        elif op == "test":
            bits = size_of(args[0])
            lines.append("    set_logic(c, (%s) & (%s), %d);" % (
                val(args[0], bits), val(args[1], bits), bits))
        elif op == "cmov":
            cc, dst, src = args
            bits = size_of(dst)
            lines.append("    if (cc_true(c, \"%s\")) %s" % (cc, put(dst, val(src, bits), bits)))
        elif op == "setcc":
            cc, dst = args
            lines.append("    " + put(dst, "cc_true(c, \"%s\")" % cc, size_of(dst)))
        elif op == "jmp":
            lines.append("    goto L_%x;" % args[0])
        elif op == "jcc":
            cc, tgt = args
            lines.append("    if (cc_true(c, \"%s\")) goto L_%x;" % (cc, tgt))
        elif op == "push":
            bits = size_of(args[0]) or 8
            lines.append("    c->r[RSP] -= 8;")
            lines.append("    wr(c, c->r[RSP], 8, %s);" % val(args[0], bits))
        elif op == "pop":
            bits = size_of(args[0]) or 8
            lines.append("    " + put(args[0], "rd(c, c->r[RSP], 8)", bits))
            lines.append("    c->r[RSP] += 8;")
        elif op == "ret":
            lines.append("    return c->r[RAX]; /* ret %d */" % args[0])
        elif op == "call":
            lines.append("    /* call 0x%x: host stub not implemented in spike */" % args[0])
        elif op == "xchg":
            a, b = args
            bits = size_of(a)
            lines.append("    { uint64_t t_ = %s; %s %s %s }" % (
                val(a, bits), put(a, val(b, bits), bits), put(b, "t_", bits), ""))
        elif op in ("nop", "cwd"):
            pass
        else:
            lines.append("    /* unsupported IR op %s */" % op)

    head = ["void f_%x(Cpu *c) {" % start] if not any(i["op"] == "ret" for i in items) else [
        "uint64_t f_%x(Cpu *c) {" % start]
    return "\n".join(head + lines + ["}"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("funcs", nargs="+", help="f_<rva> names")
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "docs", "recon", "c"))
    args = ap.parse_args()

    pe = PE(args.exe)
    rva, size = pe.dirs[3]
    off = pe.off(rva)
    funcs = {}
    for i in range(size // 12):
        begin, end, _ = __import__("struct").unpack_from("<III", pe.raw, off + 12 * i)
        if begin and end > begin:
            funcs[begin] = end
    img = bytearray(pe.size_of_image)
    for s in pe.sections:
        src = pe.raw[s["raw_ptr"]:s["raw_ptr"] + s["raw_size"]]
        img[s["vaddr"]:s["vaddr"] + len(src)] = src

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True

    os.makedirs(args.out_dir, exist_ok=True)
    files = []
    for f in args.funcs:
        m = re.fullmatch(r"f_([0-9a-fA-F]+)", f)
        if not m:
            raise SystemExit("bad function name %r" % f)
        start = int(m.group(1), 16)
        end = funcs.get(start)
        if end is None:
            print("f_%x: not a function" % start)
            continue
        try:
            items = lift_function(md, img, start, end, base=pe.image_base)
        except Unsupported as exc:
            print("f_%x: lift gap: %s" % (start, exc))
            continue
        code = [PREAMBLE, "", emit(items, start, end), ""]
        path = os.path.join(args.out_dir, "f_%x.c" % start)
        with open(path, "w", encoding="utf8") as fh:
            fh.write("\n".join(code))
        files.append(path)
        print("f_%x: %d IR ops -> %s" % (start, len(items), path))
    return 0 if files else 1


if __name__ == "__main__":
    sys.exit(main())
