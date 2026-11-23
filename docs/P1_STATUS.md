# Phase 1 status: x64 → C lift spike

This is a **spike**, not a port yet. It establishes that machine code from
`wmn6r.exe` can be lifted to C automatically and checked against the original
bytes, without a symbol table or a decompiler.

## What exists

| file | role |
|---|---|
| `tools/x64/string_xref.py` | linear sweep of `.text` with capstone; maps RIP-relative string operands to the containing `.pdata` function |
| `tools/x64/name_table.py` | scans `.rdata`/`.data` for string-pointer runs and for `luaL_Reg`-style `{char *name; void *fn}` records |
| `tools/x64/bindings.py` | merges those two into `docs/recon/BINDINGS.md` + `bindings.json` |
| `tools/x64/func_disasm.py` | annotated disassembly of one function (strings, IAT, callee names) |
| `tools/x64/simple_funcs.py` | finds small leaf/branchy functions to test the lifter on |
| `tools/x64/lift.py` | x86-64 instruction → short IR (explicit registers, flags, memory) |
| `tools/x64/interp.py` | IR interpreter, the semantic reference for the emitter |
| `tools/x64/emit_c.py` | same IR → C |
| `tools/x64/difftest.py` | runs the real bytes under Unicorn and the IR under `interp.py`, compares all 16 GPRs and scratch/stack bytes |
| `tools/x64/x86model.py` | shared register/flag/memory model |

## Bindings recovered

219 Lua-called names are visible in the game's Lua scripts. None of them is a
PE symbol. All 219 now have a location:

- **195** are loaded directly by a function (usually `lea r8, [rip+…]` with the
  name, followed by a call to a field-lookup helper). Example: `ColorMax` →
  `f_c9a40`.
- **24** occur only in pointer tables in `.rdata`; the function that loads the
  table is the implementation. The biggest groups are the clip/polygon getters
  (`DistClip_*`, `HideClip_*`, `Effect_*`, `Fog_*`, `Shadow_*`, `Tunnel_*`) and
  the three `GetCarVinylBlendParameter*` names.
- A separate 12-entry `luaL_Reg` table at `0x1e1a070` binds the sound API
  (`PlaySE`, `PlaySELoop`, …), confirming the layout used by the engine.

See `docs/recon/BINDINGS.md`, `XREFS.md` and `NAME_TABLE.md`.

## Differential test

    13 functions × 30 random contexts = 390 comparisons, all matching

The set includes straight-line code, conditionals (`je`, `jne`, `jbe`, `jb`,
`setne`, `cmovl`) and read-modify-write of memory. A failure means either a lift
bug or a setup bug; this loop already caught two:

1. `dec` was lifted as `a - 0xffffffff` instead of `a - 1` (found via `f_bf00`).
2. Unicorn and the interpreter disagreed about the initial stack slot (found via
   `f_5844`).

Run it with:

    python tools/x64/difftest.py f_8555 f_bf00 f_1d7bb --seeds 30
    python tools/x64/emit_c.py f_8555 f_bf00

C output goes to `docs/recon/c/` (gitignored).

## Gaps, in order

1. **Calls.** `call` is lifted but not executed by the spike interpreter; a
   call-graph walk and Windows-x64 argument/register clobber modelling are next.
2. **Fragments.** Some `.pdata` entries are chunks of a larger function: their
   branch target is another `.pdata` start. `difftest.py` reports them as
   fragments instead of comparing.
3. **Floating point and SIMD.** D3D/math code uses XMM (`movaps`, `cvtps2pd`,
   `andpd`, …) which the IR does not cover yet.
4. **Decompiler.** Ghidra headless 12.2 was tried three times on the 33 MB exe.
   All three died with `OutOfMemoryError` inside `AddressTableAnalyzer` (even
   with `-Xmx12G`), alongside a flood of `DemangledVariable` errors. A
   `preScript` (`tools/ghidra/DisableHeavyAnalyzers.java`) now disables the
   address-table and Microsoft demangler analyzers; the re-run was started
   separately. REA still reports the Ghidra provider as `not_configured`
   because the `opencode` process was launched before `GHIDRA_INSTALL_DIR` was
   set; a full restart is needed. None of this blocks the lift spike above.
