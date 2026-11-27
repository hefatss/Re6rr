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
| `tools/ghidra/DisableHeavyAnalyzers.java` | preScript that turns off the two analyzers that OOM on this binary |
| `tools/ghidra/ExportDecomp.java` | decompiles a list of `.pdata` ranges from the analysed project into `docs/recon/ghidra_c/` |
| `tools/ghidra/PrintOptions.java`, `Probe*.java` | option dump and diagnostics used while getting headless Ghidra to work |

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

    16 functions × 20 random contexts = 320 comparisons, all matching
    2 functions × 20 bounded contexts = 40 comparisons, all matching
    The same 18 functions with `--bounded` = 360 comparisons, all matching

The set includes straight-line code, conditionals (`je`, `jne`, `jbe`, `jb`,
`setne`, `cmovl`), read-modify-write of memory and direct calls to lifted leaf
helpers (`f_c566f0`, `f_6eef20`, `f_c58590`). A failure means either a lift bug
or a setup bug; this loop already caught four:

1. `dec` was lifted as `a - 0xffffffff` instead of `a - 1` (found via `f_bf00`).
2. Unicorn and the interpreter disagreed about the initial stack slot (found via
   `f_5844`).
3. The IR interpreter's `ret` popped the callee frame but did not advance the
   caller past its `call`, so direct calls looped forever (found via
   `f_c566f0`).
4. Unicorn's sentinel hook overwrote the return address of *every* `ret`,
   including a callee's, so the caller never resumed. The hook now tracks call
   depth.

Run it with:

    python tools/x64/difftest.py f_8555 f_bf00 f_1d7bb --seeds 30
    python tools/x64/difftest.py f_584f60 f_9e3650 --bounded --seeds 20
    python tools/x64/emit_c.py f_8555 f_bf00

C output goes to `docs/recon/c/` (gitignored).

## Ghidra decompiler

Headless Ghidra 12.2 now works on the full 33 MB exe. Three earlier runs OOM'd
in `AddressTableAnalyzer` even at `-Xmx12G` and flooded the log with
`DemangledVariable` errors. `DisableHeavyAnalyzers.java` disables those two
analyzers; the successful run finished auto-analysis in ~14 minutes and created
138,720 functions. `ExportDecomp.java` then decompiled 12 of 19 sample ranges;
the other 7 are `.pdata` entries where Ghidra refuses to disassemble, so their
output is `halt_baddata()` and is reported as a failure. Decompiled C lands in
`docs/recon/ghidra_c/` (gitignored).

REA still reports the Ghidra provider as `not_configured`: the `opencode`
process was launched before `GHIDRA_INSTALL_DIR` was set. A full restart of both
opencode processes is needed for that path. None of this blocks the lift spike.

## Gaps, in order

1. **Indirect calls / host stubs.** Direct calls to lifted functions work;
   calls through the IAT or a vtable still need a host-call model.
2. **Fragments.** Some `.pdata` entries are chunks of a larger function: their
   branch target is another `.pdata` start. `difftest.py` reports them as
   fragments instead of comparing.
3. **Bounded contexts.** `--bounded` aligns `rcx`/`rdx`/`r8` for the two
   `memcpy`-style samples. Other functions still need per-function ranges when
   their exit condition depends on register relationships.
4. **Floating point and SIMD.** D3D/math code uses XMM (`movaps`, `cvtps2pd`,
   `andpd`, …) which the IR does not cover yet.
