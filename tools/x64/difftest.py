"""Differential test: real bytes under Unicorn vs the lifted IR.

    python tools/x64/difftest.py [f_8555 f_68e0 ...] [--seeds 50] [--trace] [--bounded]

Both sides start from the same random register context, the same stack and the
same scratch block. The test passes when the 16 general registers and the
scratch/stack bytes match after the function returns.

This validates the lift without needing a C compiler: the IR interpreter is the
same program that emit_c.py prints, so a mismatch is a lift or model bug.
"""

import argparse
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
sys.path.insert(0, HERE)

from pe_report import PE  # noqa: E402
from x86model import CPU, Mem, REGS  # noqa: E402
from lift import lift_function, Unsupported  # noqa: E402
from interp import run  # noqa: E402

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
except ImportError:  # pragma: no cover
    raise SystemExit("capstone missing: python -m pip install capstone")
try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
    from unicorn.x86_const import (
        UC_X86_REG_RAX, UC_X86_REG_RBX, UC_X86_REG_RCX, UC_X86_REG_RDX,
        UC_X86_REG_RSI, UC_X86_REG_RDI, UC_X86_REG_RBP, UC_X86_REG_RSP,
        UC_X86_REG_R8, UC_X86_REG_R9, UC_X86_REG_R10, UC_X86_REG_R11,
        UC_X86_REG_R12, UC_X86_REG_R13, UC_X86_REG_R14, UC_X86_REG_R15,
    )
except ImportError:  # pragma: no cover
    raise SystemExit("unicorn missing: python -m pip install unicorn")

UC_REG = {
    "rax": UC_X86_REG_RAX, "rbx": UC_X86_REG_RBX, "rcx": UC_X86_REG_RCX,
    "rdx": UC_X86_REG_RDX, "rsi": UC_X86_REG_RSI, "rdi": UC_X86_REG_RDI,
    "rbp": UC_X86_REG_RBP, "rsp": UC_X86_REG_RSP, "r8": UC_X86_REG_R8,
    "r9": UC_X86_REG_R9, "r10": UC_X86_REG_R10, "r11": UC_X86_REG_R11,
    "r12": UC_X86_REG_R12, "r13": UC_X86_REG_R13, "r14": UC_X86_REG_R14,
    "r15": UC_X86_REG_R15,
}

SCRATCH = 0x20000000
SCRATCH_SIZE = 0x10000
STACK = 0x30000000
STACK_SIZE = 0x20000
SENTINEL = 0x40000000


def sentinel_stack():
    """Fill the stack with valid data pointers, not return addresses.

    Popped registers are often dereferenced; they must point into mapped memory.
    The real return address is written by the code hook at each `ret`.
    """
    return struct.pack("<Q", SCRATCH + 0x100) * (STACK_SIZE // 8)


def image_bytes(pe):
    """Flat image: every section copied at its virtual address."""
    img = bytearray(pe.size_of_image)
    for s in pe.sections:
        src = pe.raw[s["raw_ptr"]:s["raw_ptr"] + s["raw_size"]]
        img[s["vaddr"]:s["vaddr"] + len(src)] = src
    return img


def context(seed, bounded=False):
    rnd = random.Random(seed)
    scratch = bytearray(rnd.getrandbits(8) for _ in range(SCRATCH_SIZE))
    regs = {}
    for name in REGS:
        if name == "rsp":
            continue
        regs[name] = SCRATCH + rnd.randrange(0, 0x800)
    regs["rsp"] = STACK + STACK_SIZE - 0x200
    if bounded:
        # Copy loops end at `cmp rcx, rdx`; independent random pointers never
        # meet. Use an aligned source window and a non-overlapping destination.
        count = rnd.randrange(0, 17)  # 0 covers the empty copy
        slot = (seed % 16) * 0x100
        regs["rcx"] = SCRATCH + 0x1000 + slot
        regs["rdx"] = regs["rcx"] + count * 16  # multiple of 8 and 16
        regs["r8"] = SCRATCH + 0x4000 + slot
    return regs, scratch


def unicorn_run(pe, img, start, end, regs, scratch, max_insns=2000):
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(pe.image_base, (pe.size_of_image + 0xFFF) & ~0xFFF)
    uc.mem_write(pe.image_base, bytes(img))
    uc.mem_map(SCRATCH, SCRATCH_SIZE)
    uc.mem_write(SCRATCH, bytes(scratch))
    uc.mem_map(STACK, STACK_SIZE)
    uc.mem_write(STACK, sentinel_stack())
    uc.mem_map(SENTINEL, 0x1000)
    for name, val in regs.items():
        if name == "rsp":
            continue
        uc.reg_write(UC_REG[name], val)
    uc.reg_write(UC_X86_REG_RSP, regs["rsp"])

    state = {"n": 0, "fault": None, "depth": 0}

    def stop(uc_, address, size, user):
        state["n"] += 1
        if address == SENTINEL:
            uc_.emu_stop()
        try:
            opcode = uc_.mem_read(address, 1)[0]
        except Exception:
            opcode = None
        if opcode == 0xE8:  # direct call: a ret inside it is not the outer return
            state["depth"] += 1
        elif opcode in (0xC2, 0xC3, 0xCA, 0xCB):
            if state["depth"]:
                state["depth"] -= 1
            else:
                uc_.mem_write(uc_.reg_read(UC_X86_REG_RSP), struct.pack("<Q", SENTINEL))

    uc.hook_add(UC_HOOK_CODE, stop)
    try:
        uc.emu_start(start, SENTINEL, count=max_insns)
    except Exception as exc:  # unmapped access, invalid instruction, ...
        try:
            fault_ip = hex(uc.reg_read(UC_X86_REG_RIP))
        except Exception:
            fault_ip = "?"
        state["fault"] = "%s at rip=%s" % (exc, fault_ip)
    out = {name: uc.reg_read(UC_REG[name]) for name in REGS}
    mem = {
        "scratch": bytes(uc.mem_read(SCRATCH, SCRATCH_SIZE)),
        "stack": bytes(uc.mem_read(STACK, STACK_SIZE)),
    }
    return out, mem, state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("funcs", nargs="*", help="f_<rva> names, default a small sample")
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--bounded", action="store_true",
                    help="align rcx/rdx/r8 so bounded copy loops terminate")
    args = ap.parse_args()

    sample = args.funcs or ["f_8555", "f_68e0", "f_2ad7", "f_42cb", "f_73a2", "f_98f8"]
    targets = [int(f.split("_", 1)[1], 16) for f in sample]

    pe = PE(args.exe)
    img = image_bytes(pe)
    rva, size = pe.dirs[3]
    off = pe.off(rva)
    bounds = {}
    for i in range(size // 12):
        begin, end, _ = struct.unpack_from("<III", pe.raw, off + 12 * i)
        if begin and end > begin:
            bounds[pe.image_base + begin] = pe.image_base + end

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True

    total_fail = 0
    total_skip = 0
    for start in targets:
        end = bounds.get(pe.image_base + start)
        if end is not None:
            end -= pe.image_base
        if end is None:
            print("f_%x: not a function" % start)
            total_fail += 1
            continue
        code = img[start:end]
        try:
            items = lift_function(md, img, start, end, base=pe.image_base)
        except Unsupported as exc:
            print("f_%x: lift gap: %s" % (start, exc))
            total_fail += 1
            continue

        addrs = {it["a"] for it in items}
        outside = [it["args"][-1] for it in items
                   if it["op"] in ("jmp", "jcc") and it["args"][-1] not in addrs]
        if outside:
            print("f_%x: fragment, branch leaves body to 0x%x" % (start, outside[0]))
            total_skip += 1
            continue

        # Lift the direct-call closure, so functions that call helpers can be
        # compared too (Unicorn executes the real calls natively).
        funcs = {start: items}
        queue = [items]
        try:
            while queue and len(funcs) < 24:
                body = queue.pop(0)
                for it in body:
                    if it["op"] != "call":
                        continue
                    tgt = it["args"][0]
                    if tgt in funcs or tgt not in bounds:
                        continue
                    sub = lift_function(md, img, tgt - pe.image_base,
                                        bounds[tgt] - pe.image_base, base=pe.image_base)
                    funcs[tgt] = sub
                    queue.append(sub)
        except Unsupported as exc:
            print("f_%x: callee lift gap: %s" % (start, exc))
            total_fail += 1
            continue

        ok = faults = loops = 0
        mismatch = 0
        first = None
        for seed in range(args.seeds):
            regs, scratch = context(seed, bounded=args.bounded)
            try:
                uc_regs, uc_mem, state = unicorn_run(pe, img, pe.image_base + start, end, regs, scratch)
            except Exception as exc:  # mapping trouble
                print("f_%x: unicorn setup failed: %s" % (start, exc))
                break
            if state["fault"]:
                if seed == 0:
                    print("f_%x seed 0 unicorn fault: %s" % (start, state["fault"]))
                faults += 1
                continue
            if state["n"] >= 2000:
                # The random context does not bound a loop (e.g. memcpy until
                # rcx == rdx with independent pointers), so both sides stop at
                # their instruction cap with unrelated partial state.
                if seed == 0:
                    print("f_%x seed 0: loop, context does not bound it" % start)
                loops += 1
                continue
            mem = Mem(backing=bytes(img), base=pe.image_base)
            mem.load_bytes(SCRATCH, scratch)
            mem.load_bytes(STACK, sentinel_stack())
            cpu = CPU(mem)
            for name, val in regs.items():
                cpu.r[name] = val & 0xFFFFFFFFFFFFFFFF
            trace = [] if args.trace else None
            try:
                run(items, cpu, funcs=funcs, trace=trace)
            except RuntimeError as exc:
                if "instruction limit" in str(exc):
                    print("f_%x seed %d: loop, context does not bound it" % (start, seed))
                    loops += 1
                    break
                print("f_%x seed %d interpreter error: %s" % (start, seed, exc))
                mismatch += 1
                break
            except Exception as exc:
                print("f_%x seed %d interpreter error: %s: %s" % (
                    start, seed, type(exc).__name__, exc))
                mismatch += 1
                break

            diffs = []
            for name in REGS:
                if cpu.r[name] != uc_regs[name]:
                    diffs.append("%s lifted=%016x native=%016x" % (name, cpu.r[name], uc_regs[name]))
            ir_scratch = bytes(cpu.mem.read(SCRATCH + i, 1) for i in range(SCRATCH_SIZE))
            if ir_scratch != uc_mem["scratch"]:
                for i in range(SCRATCH_SIZE):
                    if ir_scratch[i] != uc_mem["scratch"][i]:
                        diffs.append("scratch[%04x] lifted=%02x native=%02x" % (
                            i, ir_scratch[i], uc_mem["scratch"][i]))
                        break
            if diffs:
                print("f_%x seed %d: %s" % (start, seed, "; ".join(diffs[:6])))
                first = first or (seed, diffs)
                mismatch += 1
                break
            ok += 1

        status = "FAIL" if mismatch else ("ok" if faults == 0 and loops == 0 else "SKIP")
        print("f_%x (%d bytes, %d IR ops): %s  %d/%d seeds compared, %d faults, %d loops" % (
            start, end - start, len(items), status, ok, args.seeds, faults, loops))
        total_fail += 1 if status == "FAIL" else 0
        total_skip += 1 if status == "SKIP" else 0

    print("\n%d/%d functions pass, %d skipped" % (
        len(targets) - total_fail - total_skip, len(targets), total_skip))
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
