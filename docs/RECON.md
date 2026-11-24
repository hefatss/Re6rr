# WMMT6RR recon — results of Phase 0

Dump: `D:\Games\W6W-05` (TeknoParrot layout, JPN rev with English patch applied)
Reports: `pe.json`, `lua.json`, `assets.json`, plus `lua_api.txt`, `formats.txt`,
`lua_summary.txt`, `assets_summary.txt` in this folder.

## Executable

| Item | Value |
|---|---|
| File | `wmn6r.exe`, 33,797,120 bytes (32.2 MiB) |
| SHA-256 | `9c35c21cc69ba8c605036402db8ef619215fef0c6a32aeb72541b51d0e69357c` |
| Format | PE32+ (x86-64), MSVC, linker 10.0, built 2022-10-20 |
| Image base / entry | `0x140000000` / RVA `0x0DEE6F0` |
| Sections | `.text` 16.5 MB, `.rdata` 11.8 MB, `.data` 2.5 MB, `.pdata` 825 KB, `.reloc` 620 KB |
| Packing | none — normal section names, full `.reloc`, `.pdata` intact |
| Functions (`.pdata`) | **70,377** (38,905 distinct unwind records) |
| Symbols | no COFF symbols; PDB path only: `C:\jenkins\sharedspace\trunk_wmn6RR_Koshien_Product\wmn6\x64\Release\wmn6r.pdb` |
| Imports | 28 DLLs / 825 symbols: d3d11, dxgi, D3DCOMPILER_43, lua5.1, SDL2-side libs (`nuSound2_win64`), `Wg6Enma_Release_IDL0`, `bngrw`, `hasp_windows_x64_30382`, MF/MFPlat/MFReadWrite, WS2_32/MSWSOCK, dbghelp |
| Exports | 2 |
| TLS | one callback at `0x140E1BE60` |
| Relocations | 1,833 blocks / 270,128 entries |

Consequence: static recompilation is tractable in principle (function boundaries are
exact), but needs an **x86-64 PE** backend. `super3dxplus/tools/recomp` is i386 ELF
and selective by mangled symbol; it cannot be reused as-is. No symbols means roots
must come from imports, string references, RTTI and pattern matching.

## Assets

`data` = 10,834 files / 8.25 GiB. `data_jp` = 13,624 files / 5.22 GiB.

| Ext | Count | Size | Container |
|---|---|---|---|
| `.lua` | 4,885 | 154 MB | plain text, mostly data tables (car spec/colour/position/vinyl, course clip lists) |
| `.bin` | 1,495 | 2.80 GB | raw float32 course geometry (some gzip) |
| `.nut` | 580 + 10,571 | 1.18 GB + 1.94 GB | gzip, inner `NTWD` (model/scene) |
| `.tex` | 1,175 + 75 | 406 MB | gzip, inner `XMD` |
| `.mdl` | 578 + 32 | 188 MB | gzip, inner `XMD.001` |
| `.nub` | 149 | 3.45 GB | raw sound banks (`data/sound/BGM...`) |
| `.ees` | 1,129 | 2.89 GB | raw, header `0x2712` — scene camera/event data |
| `.nud` | 371 | 6.2 MB | `NDWD` — navimap |
| `.nsh` | 257 | 1.4 MB | `NSXR` — compiled shader blobs |
| `.act` | 170 | 6.8 MB | `RESOURCE:NU` — effect actors |
| `.lmd` | 985 | 13 MB | gzip — flash UI |
| `.xmlt` | 591 | 1.0 MB | XML text (story lines, cut-in tables) |
| `.nuf` | 1 | 9.5 KB | `NUF` — font (`engine/default_font`) |
| `.med` | 28 + 39 | 3.9 MB | motion data |

Gzip is a plain gzip stream (no encryption detected on samples). Inner formats
(`NTWD`, `XMD`, `NDWD`, `NSXR`) still need per-format parsers.

`.nub` is now decoded: 32-byte header, tone-record offsets, 208-byte records with
PCM length/offset and WAV format, then raw interleaved PCM. All 149 banks parse
(781 tones); `tools/engine/nub_audio.py` inventories them and extracts original
PCM to standard WAV. Format details and unresolved mixer fields are in
`recon/AUDIO_NUB.md`.

Shader folder holds compiled blobs (`NSXR`), not HLSL source, so a port translates
behaviour rather than recompiling shaders.

## Lua

- 4,885 scripts in `data`, 167 in `data_jp`; text, no `require` usage, no bytecode.
- Content is data: car specification (151 files), car positions (255), colours,
  vinyl/sticker tables, course clip lists (`course/stage/*/clip`), plus settings.
- 812 names defined in Lua itself; real flow logic stays in the executable.
- 219 identifiers called from Lua that exist as strings in the executable — the
  candidate native binding surface (top: `GetShaderCarVec4/Float/Int`, `GetTirePos`,
  `GetCenterPos`, `GetCustomGTWingPos`, `GetCarHightDown`, `GetCarAeroTireOffset`,
  `GetGTWing*`, `IsVinylSelectOriginal`, `getVinylColor`, `getMiniStickerColor`,
  `ColorMax`, course queries `GetAreaId`, `GetCameraDirection`, `GetPathList`,
  `GetRelatedSection`, `HideClip_*`, `DistClip_*`, effect queries `GetAura_*`,
  `GetAfterFire_*`). Full list in `lua_api.txt`.
- Extraction needed a CP932 fallback; the first pass (UTF-8 only) produced noise.

## English patch

Patch replaces text in `data_jp/**/*.xmlt` (verified: `Message.xmlt` is English
prose, `Event.xmlt` still has Japanese romaji ids). `data_msgdb` remains an `.xlsm`
spreadsheet in both roots. `data_en/` is empty in this dump.

## Function map (`.pdata` → `pdata.json`)

- 70,377 functions, 14.7 MB of code inside a 16.5 MB `.text` (the rest is padding
  and data-free alignment).
- 11,796 functions carry a chained unwind record (the compiler shared unwind data);
  only 3 are declared leaf, since MSVC omits `.pdata` for real leaves.
- Size: min 2, median 88, max 60,258 bytes. Histogram: `<16` 2,564; `16-31`
  10,902; `32-63` 16,380; `64-127` 14,499; `128-255` 13,639; `256-1023` 10,422;
  `>=1024` 1,971. Biggest: `0xA73E10` (60,258), `0x1019BB0` and `0x1026520`
  (51,563 each).

## Tooling reached

- Python 3.14 available; `pefile` not installed — `pe_report.py` parses PE itself.
- LLVM binutils at `C:\Program Files\LLVM\bin` (`llvm-readobj`, works on the PE).
- REA: static PE helpers work (`inspect_pe_imports` recorded), but no deep-analysis
  provider was configured — Ghidra needs `GHIDRA_INSTALL_DIR` (12.1+), Hopper is
  macOS-only, IDA/Kuna absent, and Kuna does not admit PE yet.
- Ghidra 12.2 PUBLIC installed at `C:\Tools\ghidra_12.2_PUBLIC` (win_x86_64
  decompiler present, `analyzeHeadless.bat` runs with JDK 21/25). User env
  `GHIDRA_INSTALL_DIR` set. REA has to be restarted before it offers the provider.
- Full auto-analysis on Windows OOMs in `AddressTableAnalyzer` with the default
  2G heap. Durable route is WSL2 Debian: Node 24 + Temurin JDK 25 under
  `/home/rap/.local/re6-tools`, Ghidra launched from the same
  `/mnt/c/Tools/ghidra_12.2_PUBLIC`, project at `/home/rap/rea-ghidra/wmn6r.gpr`.
  Import once with `-noanalysis`; REA 6.9.0 then opens that project with
  `REA_GHIDRA_PROJECT_PATH=/home/rap/rea-ghidra/wmn6r.gpr`,
  `REA_GHIDRA_PROGRAM_NAME=wmn6r.exe`, `GHIDRA_INSTALL_DIR=/mnt/c/Tools/ghidra_12.2_PUBLIC`
  and decompiles individual addresses without repeat import. Full analysis uses
  `GHIDRA_HEADLESS_MAXMEM=8G` plus `-preScript tools/ghidra/DisableHeavyAnalyzers.java`.
  `MAXMEM` is not the knob `analyzeHeadless` reads.

## Phase 1 plan (recompiler spike), now concrete

1. Map PE: RVA→file offset table, `.pdata` function list, unwind info parsing for
   stack frame sizes (`UNWIND_INFO`), import IAT slots, TLS callback.
2. Recover roots: scan `.rdata` for the Lua-visible names above, follow their
   registration path to the C functions; classify by module (car, course, effect).
3. Translate a first function set to C: leaf/math helpers first, then a
   `GetTirePos`-like getter chain; compare against a reference run
   (Unicorn/emulation harness) on random inputs.
4. Measure: instructions decoded, unsupported opcodes, code size covered, before
   committing to full function coverage.

## Phase 2 plan (assets), now concrete

1. gzip unwrap + `NTWD`/`XMD` chunk walker (start with `data/car/**/*.mdl` and one
   `.tex`).
2. Course geometry: `.bin` float32 sections + `course/path` + navimap `NDWD`.
3. Viewer: load one car and one course section, render with a throwaway Vulkan/GL
   path before any engine work.
