"""Interpret the IR produced by lift.py.

This is the reference side of the differential test: the same IR that emit_c.py
turns into C is executed here over the shared CPU/Mem model, so a lift bug shows
up as a register/memory mismatch against Unicorn running the real bytes.
"""

from x86model import CPU, MASK, canon, sxt


def size_of(op):
    if op[0] == "reg":
        return canon(op[1])[2]
    if op[0] == "mem":
        return op[5]
    return None


def ea(cpu, op):
    """Effective address of ("mem", base, index, scale, disp, bits)."""
    _, base, index, scale, disp = op[:5]
    addr = disp
    if isinstance(base, int):
        addr += base
    elif base is not None:
        addr += cpu.r[base]
    if index is not None:
        addr += cpu.r[index] * (scale or 1)
    return addr & MASK[64]


def read(cpu, op, bits):
    if op[0] == "reg":
        return cpu.rd(op[1])
    if op[0] == "imm":
        return op[1] & MASK[bits]
    return cpu.mem.read(ea(cpu, op), bits // 8)


def write(cpu, op, value, bits):
    value &= MASK[bits]
    if op[0] == "reg":
        cpu.wr(op[1], value)
        return
    if op[0] == "mem":
        cpu.mem.write(ea(cpu, op), bits // 8, value)
        return
    raise AssertionError("cannot write to %r" % (op,))


def cond(cpu, cc):
    f = cpu.flags
    cc = cc or "e"
    if cc in ("e", "z"):
        return f["zf"] == 1
    if cc in ("ne", "nz"):
        return f["zf"] == 0
    if cc == "s":
        return f["sf"] == 1
    if cc == "ns":
        return f["sf"] == 0
    if cc == "o":
        return f["of"] == 1
    if cc == "no":
        return f["of"] == 0
    if cc in ("p", "pe"):
        return f["pf"] == 1
    if cc in ("np", "po"):
        return f["pf"] == 0
    if cc in ("b", "c", "nae"):
        return f["cf"] == 1
    if cc in ("ae", "nb", "nc"):
        return f["cf"] == 0
    if cc in ("be", "na"):
        return f["cf"] == 1 or f["zf"] == 1
    if cc in ("a", "nbe"):
        return f["cf"] == 0 and f["zf"] == 0
    if cc in ("l", "nge"):
        return f["sf"] != f["of"]
    if cc in ("ge", "nl"):
        return f["sf"] == f["of"]
    if cc in ("le", "ng"):
        return f["zf"] == 1 or f["sf"] != f["of"]
    if cc in ("g", "nle"):
        return f["zf"] == 0 and f["sf"] == f["of"]
    raise AssertionError("unknown condition %r" % cc)


def run(items, cpu, limit=100000, trace=None):
    """Execute until ret (or the program counter leaves the lifted body)."""
    labels = {}
    for i, it in enumerate(items):
        labels.setdefault(it["a"], i)

    pc = 0
    steps = 0
    while pc < len(items):
        it = items[pc]
        if trace is not None:
            trace.append(it)
        op, args = it["op"], it["args"]
        cpu.rip = it["a"]
        steps += 1
        if steps > limit:
            raise RuntimeError("instruction limit in IR interpreter")

        if op == "mov":
            bits = size_of(args[0])
            write(cpu, args[0], read(cpu, args[1], bits), bits)
        elif op == "movzx":
            bits = size_of(args[0])
            write(cpu, args[0], read(cpu, args[1], size_of(args[1])), bits)
        elif op == "movsx":
            sb = size_of(args[1])
            bits = size_of(args[0])
            write(cpu, args[0], sxt(read(cpu, args[1], sb), sb) & MASK[bits], bits)
        elif op == "lea":
            bits = size_of(args[0])
            _, base, index, scale, disp = args[1]
            addr = disp
            if isinstance(base, int):
                addr += base
            elif base is not None:
                addr += cpu.r[base]
            if index is not None:
                addr += cpu.r[index] * (scale or 1)
            write(cpu, args[0], addr, bits)
        elif op == "bin":
            name, dst, a_op, b_op = args
            bits = size_of(dst)
            a = read(cpu, a_op, bits)
            b = read(cpu, b_op, bits)
            if name in ("add", "sub"):
                res = cpu.set_add(a, b, bits, sub=(name == "sub"))
            elif name in ("adc", "sbb"):
                b2 = b + cpu.flags["cf"]
                res = cpu.set_add(a, b2, bits, sub=(name == "sbb"))
            elif name in ("and", "or", "xor"):
                res = {"and": a & b, "or": a | b, "xor": a ^ b}[name]
                cpu.set_logic(res, bits)
            elif name == "imul":
                sa, sb = sxt(a, bits), sxt(b, bits)
                res = (sa * sb) & MASK[bits]
                cpu.set_logic(res, bits)
                cpu.flags["of"] = cpu.flags["cf"] = int(res != (sa * sb))
            elif name in ("shl", "shr", "sar"):
                cnt = b & 0x3F
                if name == "shl":
                    res = a << cnt
                    cpu.flags["cf"] = (a >> (bits - cnt)) & 1 if cnt else cpu.flags["cf"]
                elif name == "shr":
                    res = a >> cnt
                    cpu.flags["cf"] = (a >> (cnt - 1)) & 1 if cnt else cpu.flags["cf"]
                else:
                    res = sxt(a, bits) >> cnt
                    cpu.flags["cf"] = (sxt(a, bits) >> (cnt - 1)) & 1 if cnt else cpu.flags["cf"]
                res &= MASK[bits]
                cpu.flags["zf"] = int(res == 0)
                cpu.flags["sf"] = (res >> (bits - 1)) & 1
            else:
                raise AssertionError("bin op %r" % name)
            write(cpu, dst, res, bits)
        elif op == "un":
            name, dst, a_op = args
            bits = size_of(dst)
            a = read(cpu, a_op, bits)
            if name == "not":
                res = ~a
            elif name == "neg":
                res = cpu.set_add(0, a, bits, sub=True)
            elif name in ("inc", "dec"):
                cf = cpu.flags["cf"]
                res = cpu.set_add(a, 1, bits, sub=(name == "dec"))
                cpu.flags["cf"] = cf
            elif name == "bswap":
                res = int.from_bytes(a.to_bytes(bits // 8, "little"), "big")
            else:
                raise AssertionError("un op %r" % name)
            write(cpu, dst, res, bits)
        elif op == "cmp":
            bits = size_of(args[0])
            cpu.set_add(read(cpu, args[0], bits), read(cpu, args[1], bits), bits, sub=True)
        elif op == "test":
            bits = size_of(args[0])
            cpu.set_logic(read(cpu, args[0], bits) & read(cpu, args[1], bits), bits)
        elif op == "cmov":
            cc, dst, src = args
            if cond(cpu, cc):
                bits = size_of(dst)
                write(cpu, dst, read(cpu, src, bits), bits)
        elif op == "setcc":
            cc, dst = args
            write(cpu, dst, 1 if cond(cpu, cc) else 0, size_of(dst))
        elif op == "jmp":
            tgt = args[0]
            if tgt not in labels:
                return cpu  # leaving the function
            pc = labels[tgt]
            continue
        elif op == "jcc":
            cc, tgt = args
            if cond(cpu, cc):
                if tgt not in labels:
                    return cpu
                pc = labels[tgt]
                continue
        elif op == "push":
            bits = size_of(args[0]) or 8
            val = read(cpu, args[0], bits)
            cpu.r["rsp"] = (cpu.r["rsp"] - 8) & MASK[64]
            cpu.mem.write(cpu.r["rsp"], 8, val & MASK[64])
        elif op == "pop":
            bits = size_of(args[0]) or 8
            val = cpu.mem.read(cpu.r["rsp"], 8)
            cpu.r["rsp"] = (cpu.r["rsp"] + 8) & MASK[64]
            write(cpu, args[0], val, bits)
        elif op == "ret":
            cpu.r["rsp"] = (cpu.r["rsp"] + 8 + args[0]) & MASK[64]
            return cpu
        elif op == "call":
            cpu.r["rsp"] = (cpu.r["rsp"] - 8) & MASK[64]
            cpu.mem.write(cpu.r["rsp"], 8, args[0] & MASK[64])
            raise AssertionError("call in the interpreter spike")
        elif op == "xchg":
            a, b = args
            bits = size_of(a)
            va, vb = read(cpu, a, bits), read(cpu, b, bits)
            write(cpu, a, vb, bits)
            write(cpu, b, va, bits)
        elif op == "cwd":
            pass
        elif op == "nop":
            pass
        else:
            raise AssertionError("unknown IR op %r" % op)
        pc += 1
    return cpu
