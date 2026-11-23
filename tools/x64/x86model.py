"""Register and memory model shared by the lifter, the interpreter and the C emitter.

Only what the recompiler needs: the 16 general registers as 64-bit values with
x86 sub-register read/write rules, the flags we can derive, and a flat memory
whose byte values live in a dict so unmapped reads are visible instead of silent.
"""

REGS = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]

# sub-register -> (parent, shift, bits)
SUB = {"rax": ("rax", 0, 64), "eax": ("rax", 0, 32), "ax": ("rax", 0, 16),
       "al": ("rax", 0, 8), "ah": ("rax", 8, 8)}
for _p, _names in {
    "rcx": ("ecx", "cx", "cl", "ch"),
    "rdx": ("edx", "dx", "dl", "dh"),
    "rbx": ("ebx", "bx", "bl", "bh"),
}.items():
    SUB[_names[0]] = (_p, 0, 32)
    SUB[_names[1]] = (_p, 0, 16)
    SUB[_names[2]] = (_p, 0, 8)
    SUB[_names[3]] = (_p, 8, 8)
SUB.update({
    "esp": ("rsp", 0, 32), "sp": ("rsp", 0, 16), "spl": ("rsp", 0, 8),
    "ebp": ("rbp", 0, 32), "bp": ("rbp", 0, 16), "bpl": ("rbp", 0, 8),
    "esi": ("rsi", 0, 32), "si": ("rsi", 0, 16), "sil": ("rsi", 0, 8),
    "edi": ("rdi", 0, 32), "di": ("rdi", 0, 16), "dil": ("rdi", 0, 8),
})
for _i in range(8, 16):
    _p = "r%d" % _i
    SUB[_p] = (_p, 0, 64)
    SUB[_p + "d"] = (_p, 0, 32)
    SUB[_p + "w"] = (_p, 0, 16)
    SUB[_p + "b"] = (_p, 0, 8)

MASK = {8: 0xFF, 16: 0xFFFF, 32: 0xFFFFFFFF, 64: 0xFFFFFFFFFFFFFFFF}


def canon(name):
    """Register name -> (parent, shift, bits), including canonical 64-bit names."""
    if name in SUB:
        return SUB[name]
    if name in REGS:
        return (name, 0, 64)
    raise KeyError(name)


class Mem:
    """Flat memory keyed by address; page granularity for dirty tracking.

    `backing` is an optional bytes-like image already mapped at `base`, so a
    whole PE can be readable without materialising one dict entry per byte.
    """

    def __init__(self, backing=None, base=0):
        self.b = {}
        self.dirty = set()
        self.backing = backing
        self.base = base

    def _get(self, addr):
        v = self.b.get(addr)
        if v is not None:
            return v
        if self.backing is not None:
            i = addr - self.base
            if 0 <= i < len(self.backing):
                return self.backing[i]
        return 0

    def read(self, addr, size):
        return int.from_bytes(bytes(self._get(addr + i) for i in range(size)), "little")

    def write(self, addr, size, value):
        value &= MASK[size * 8]
        for i in range(size):
            self.b[addr + i] = (value >> (8 * i)) & 0xFF
        self.dirty.add(addr >> 12)

    def load_bytes(self, addr, data):
        for i, byte in enumerate(data):
            self.b[addr + i] = byte

    def page_bytes(self, page):
        out = {}
        base = page << 12
        for a in range(base, base + 4096):
            if a in self.b:
                out[a] = self.b[a]
        return out


def sxt(value, bits):
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


class CPU:
    """Register file + flags, enough to interpret and to emit C."""

    def __init__(self, mem=None):
        self.r = {name: 0 for name in REGS}
        self.rip = 0
        self.mem = mem or Mem()
        self.flags = {"cf": 0, "pf": 0, "af": 0, "zf": 0, "sf": 0, "of": 0}
        self.cmp_bits = 32
        self.cmp_signed = False

    # ---- register access ----
    def rd(self, name):
        parent, shift, bits = canon(name)
        v = (self.r[parent] >> shift) & MASK[bits]
        return v

    def wr(self, name, value):
        parent, shift, bits = canon(name)
        value &= MASK[bits]
        cur = self.r[parent]
        if shift:
            cur &= ~(MASK[bits] << shift)
            cur |= value << shift
        elif bits == 64:
            cur = value
        else:
            cur &= ~MASK[bits]
            cur |= value
        self.r[parent] = cur & MASK[64]

    # ---- flags ----
    def set_logic(self, result, bits):
        result &= MASK[bits]
        self.flags["cf"] = 0
        self.flags["of"] = 0
        self.flags["zf"] = int(result == 0)
        self.flags["sf"] = (result >> (bits - 1)) & 1

    def set_add(self, a, b, bits, sub=False):
        m = MASK[bits]
        if sub:
            full = (a & m) - (b & m)
            res = full & m
            carry = int((a & m) < (b & m))
            ov = int(((a ^ b) & (a ^ res) & (1 << (bits - 1))) != 0)
        else:
            full = (a & m) + (b & m)
            res = full & m
            carry = int(full > m)
            ov = int((~(a ^ b) & (a ^ res) & (1 << (bits - 1))) != 0)
        self.flags["cf"] = carry
        self.flags["of"] = ov
        self.flags["zf"] = int(res == 0)
        self.flags["sf"] = (res >> (bits - 1)) & 1
        self.cmp_bits = bits
        return res
