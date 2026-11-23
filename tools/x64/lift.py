"""Lift one x86-64 instruction into a short list of IR statements.

IR statements are dicts: {"a": address, "op": name, "args": [...]}.
Operands:

    ("reg", "rax")                     register, 64-bit parent name
    ("imm", value)                     immediate
    ("mem", base, index, scale, disp, bits)   base/index are register names or None
    ("ea", base, index, scale, disp)          effective address, for `lea`

`base` may already be an absolute address when the instruction used RIP-relative
addressing, in which case base is an int and index is None.

The lift is deliberately narrow: it covers the integer subset the small leaf
functions use. Anything else raises Unsupported so callers see the gap instead
of silently wrong C.
"""


class Unsupported(Exception):
    pass


def _reg(insn, name):
    return ("reg", name)


def _operand(insn, op):
    import capstone.x86 as X
    if op.type == X.X86_OP_REG:
        return ("reg", insn.reg_name(op.reg))
    if op.type == X.X86_OP_IMM:
        return ("imm", op.imm)
    if op.type == X.X86_OP_MEM:
        bits = op.size * 8
        base = None
        index = None
        scale = op.mem.scale or 1
        if op.mem.base:
            bname = insn.reg_name(op.mem.base)
            if bname == "rip":
                base = insn.address + insn.size + op.mem.disp
                disp = 0
                return ("mem", base, None, 1, disp, bits)
            base = bname
        if op.mem.index:
            index = insn.reg_name(op.mem.index)
        return ("mem", base, index, scale, op.mem.disp, bits)
    raise Unsupported("operand type %d" % op.type)


def _cc(mnemonic, prefixes):
    for p in prefixes:
        if mnemonic == p:
            return None
        if mnemonic.startswith(p):
            return mnemonic[len(p):]
    return None


BIN = {"add": "add", "sub": "sub", "and": "and", "or": "or", "xor": "xor",
       "imul": "imul", "shl": "shl", "sal": "shl", "shr": "shr", "sar": "sar",
       "rol": "rol", "rcr": "rcr", "adc": "adc", "sbb": "sbb"}
UN = {"neg": "neg", "not": "not", "inc": "inc", "dec": "dec",
      "bswap": "bswap"}


def lift(insn, signed_cmp=None):
    """Return list of IR statements for `insn` (capstone instruction)."""
    m = insn.mnemonic
    ops = insn.operands
    out = []

    def st(op, *args):
        out.append({"a": insn.address, "op": op, "args": list(args)})

    if m in ("nop", "endbr64", "int3", "hlt", "ud2", "pause"):
        st("nop")
        return out
    if m in ("mov", "movabs"):
        dst, src = _operand(insn, ops[0]), _operand(insn, ops[1])
        st("mov", dst, src)
        return out
    if m in ("movzx", "movzb", "movzw"):
        st("movzx", _operand(insn, ops[0]), _operand(insn, ops[1]))
        return out
    if m in ("movsx", "movsxd", "movsb", "movsw"):
        st("movsx", _operand(insn, ops[0]), _operand(insn, ops[1]))
        return out
    if m == "lea":
        dst = _operand(insn, ops[0])
        src = _operand(insn, ops[1])
        if src[0] != "mem":
            raise Unsupported("lea without memory operand")
        st("lea", dst, ("ea", src[1], src[2], src[3], src[4]))
        return out
    if m in ("cmp", "test"):
        st(m, _operand(insn, ops[0]), _operand(insn, ops[1]))
        return out
    if m in BIN:
        if len(ops) == 3:  # three-operand imul
            st("bin", BIN[m], _operand(insn, ops[0]), _operand(insn, ops[1]), _operand(insn, ops[2]))
        elif len(ops) == 2:
            st("bin", BIN[m], _operand(insn, ops[0]), _operand(insn, ops[0]), _operand(insn, ops[1]))
        elif len(ops) == 1:
            st("bin", BIN[m], _operand(insn, ops[0]), _operand(insn, ops[0]), ("imm", 1))
        else:
            raise Unsupported("arithmetic without operands: %s" % m)
        return out
    if m in UN:
        st("un", UN[m], _operand(insn, ops[0]), _operand(insn, ops[0]))
        return out
    cc = _cc(m, ("cmov",))
    if cc is not None:
        st("cmov", cc, _operand(insn, ops[0]), _operand(insn, ops[1]))
        return out
    cc = _cc(m, ("set",))
    if cc is not None:
        st("setcc", cc, _operand(insn, ops[0]))
        return out
    if m == "jmp":
        tgt = ops[0].imm if ops else None
        if tgt is None:
            raise Unsupported("indirect jmp")
        st("jmp", tgt)
        return out
    cc = _cc(m, ("j",))
    if cc is not None and ops:
        if ops[0].type != 2:  # X86_OP_IMM
            raise Unsupported("indirect jcc")
        st("jcc", cc, ops[0].imm)
        return out
    if m == "call":
        if ops and ops[0].type == 2:
            st("call", ops[0].imm)
        else:
            op = _operand(insn, ops[0])
            st("call_indirect", op)
        return out
    if m == "push":
        st("push", _operand(insn, ops[0]))
        return out
    if m == "pop":
        st("pop", _operand(insn, ops[0]))
        return out
    if m in ("ret", "retn", "rep ret"):
        st("ret", ops[0].imm if ops else 0)
        return out
    if m in ("leave",):
        st("mov", ("reg", "rsp"), ("reg", "rbp"))
        st("pop", ("reg", "rbp"))
        return out
    if m in ("cdqe", "cbw", "cwde"):
        st("movsx", ("reg", "rax"), ("reg", {"cdqe": "eax", "cwde": "eax", "cbw": "al"}[m]))
        return out
    if m in ("cqo", "cdq", "cwd"):
        st("cwd", m)
        return out
    if m == "xchg":
        a, b = _operand(insn, ops[0]), _operand(insn, ops[1])
        st("xchg", a, b)
        return out
    raise Unsupported("%s %s" % (m, insn.op_str))


def lift_function(md, code, start, end, base=0, max_insns=20000):
    """Lift `code[start:end]` with instruction addresses based at `base`."""
    items = []
    for insn in md.disasm(code[start:end], base + start):
        if insn.id == 0:
            continue
        items += lift(insn)
        if len(items) > max_insns:
            raise Unsupported("function too large to lift in the spike")
    return items
