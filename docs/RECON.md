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
| `.ees` | 1,129 | 2.89 GB | raw `EventScene2` header + typed arrays — scene camera/car data |
| `.nud` | 371 | 6.2 MB | `NDWD` — navimap |
| `.nsh` | 257 | 1.4 MB | `NSXR` — compiled shader blobs |
| `.act` | 170 | 6.8 MB | `RESOURCE:NU` — effect actors |
| `.lmd` | 985 | 13 MB | gzip — flash UI |
| `.xmlt` | 591 | 1.0 MB | XML text (story lines, cut-in tables) |
| `.nuf` | 1 | 9.5 KB | `NUF` — font (`engine/default_font`) |
| `.med` | 28 + 39 | 3.9 MB | motion data |

Gzip is a plain gzip stream (no encryption detected on samples). Inner formats
`NTWD`, `XMD` and `NDWD` have per-format parsers. `NSXR` is now decoded too:
223 `.nsh` files wrap two DXBC blobs each, with `RDEF`, `ISGN`, `OSGN`, `SHDR`
and `STAT` chunks; `tools/engine/nsxr_shader.py` inventories, extracts and parses
signatures, reflection and statistics. Shader record 0 is vertex, record 1 pixel;
varyings match. All 446 blobs target SM4 (`0x0400`), with 797 constant buffers,
2,029 variables and 1,849 resource bindings; creator is the Microsoft HLSL
compiler `9.29.952.3111`. `SHDR` instruction boundaries and opcode ids decode
cleanly: 25,758 instructions total, SM4 opcode ids `0..105`.

`.nub` is now decoded: 32-byte header, tone-record offsets, 208-byte records with
PCM length/offset and WAV format, then raw interleaved PCM. All 149 banks parse
(781 tones); `tools/engine/nub_audio.py` inventories them and extracts original
PCM to standard WAV. Native callers show `sys::Sound::Impl::playSe` selecting a
bank number and tone index before calling `nuSound2KeyOnHandle(handle, tone,
attr)`, while `registerBank` stores the nuSound2 handle in a 32-byte bank-table
entry. Shipped engine-sound lookup tables are parsed by
`tools/engine/audio_tables.py`: `engmap.tbl` is 32 x 20 u32 (320 `(engine sound,
group)` pairs, 224 ids, groups 2/3/4) and `emtis.tbl` has version `3 3 17`, seven
numbered sections and 416 source WAV names. `FUN_1407cca90` indexes ENGMAP by car `EngineSound` and tune level, and
`FUN_1407d27f0` resolves the selected EMTIS record into 16 layer tones: section
0 arrays `C[i0][2..9]`, `E[i1][1..3]`, `G[i2][1..3]` plus section 5 `J[i3][1..2]`.
`CSoundImpl::FUN_1407d0450` plays those on bank 7 (`ENGINE.nub`, 409 tones);
six request objects use bank 4 (`MISSFIRE.nub`, 6 tones). All 320 shipped
car/tune mappings resolve; group is stored but runtime layer selection is not
decoded. `tools/engine/engine_sound.py` reports the full mapping.
`SoundManager` loads `config.bin`
and `config_3d.bin`, then initialises nuSound2 with 8 banks, 34 request ids and
1 stream. `nuSound2_win64.dll` analysis also recovers 64 bank slots of stride
`0x804` and tone-record `+0x28` bit 0 as the loop flag. `sys::Sound::Impl::playSe`
uses a 0x20-stride bank table with the nuSound2 handle at bank `+0x18` and calls
`nuSound2KeyOnHandle(handle, tone, 0)`. Twelve Lua sound bindings were recovered
from the `luaL_Reg` table at `0x141e1a070`: `PlaySE` fixes bank 2 (SYSTEM),
`PlaySEOfBank` takes the bank, and Decide/Cancel/Move hardcode tones `0x2f`
(`SELECT`), `7` (`CANCEL`) and `0xf` (`CURSOR`). BGM ids `0..141` map through a
142-entry name table (`0x1414ec550`, 0x40-byte strings) and a 142-pointer path
table (`0x141e1f8e0`); id `0x8c` stops and `0x8d` is the rejected `RANDOM` id.
A second `playSe` entry point calls `nuSound2KeySetOnHandle(handle, tone,
volume, pan, flags, &key)`; `readyBank` requires bank state `3` at `+0x1c`.
`playSeLoop` uses 8-byte request records and scene sound reserves slot `0x21`
of 34; `nuSound2KeyOnHandle` defaults are volume `1.0`, pan `0.0`, flags `0`.
`FUN_1401aebc0` drives positional SE from 0x24-byte records
(bank, tone, interval, xyz). Playback ABI: BGM goes through
`nuSound2StreamStartEx(handle 0, path, 0)`; `nuSound2_win64` keeps 64 voice
slots of 0xa0 bytes with metadata at `0x2800 + slot*0xc`, while bank setup at
`FUN_18002eb80` uses 0x804-byte slots and returns distinct errors for bad index,
bad format, null data, already-set banks and voice/stream failures.
`tools/engine/audio_events.py` reads these tables and checks the dispatch ABI. No shipped Lua file calls any sound binding, but
three stage-effect parameter files declare symbolic `NUD_TONE_RACE_HANABI1/2`
names; those resolve to RACE bank 3, tones `0xe`/`0xf` and match the literals in
`FUN_1401b0cd0`. All other event → `(bank, tone)` pairs remain native
call-site constants. Format details, call sites and unresolved mixer fields
are in `recon/AUDIO_NUB.md`.

`.EES` scene files are raw, with no encryption or decompression on the native
load path. Two camera variants (`0x2712`/`0x2713`) hold 255 records of `0x50`
plus `0x160` bytes; car files hold 10,800 records of `0x180`, `0xa0` and `0x8c`
bytes. All 1,129 shipped files parse with exact size identity;
`tools/engine/ees_scene.py` inventories and extracts the arrays. Native
consumers decode camera `+0x00` type, `+0x04` int32 start frame, `+0x08` float
duration and `+0x0c` exact-frame flag (`FUN_1401c8f60`), plus car `+0x00` id,
`+0x04` flags, `+0x10` transform matrix and `+0x150` yaw
(`FUN_1401cba00`/`FUN_1401cc9d0`). `FUN_1401e0330` names 31 further camera
fields from `+0x00` to `+0x10c`, including start/end field angles, look-at
ranges and rotations, offset positions and connection ids;
`ees_fields.camera_fields()` decodes them. The `car_effect` copy ABI from the
0xa0 EES record into the 0xe0 runtime record is mapped by `FUN_1401cc390` and
modelled by `ees_fields.car_effect_copy()`, but neither its field semantics nor
the remaining camera bytes are interpreted. Details in `recon/SCENE_EES.md`.

Shader folder holds compiled DXBC blobs inside `NSXR`, not HLSL source, so a
port translates behaviour rather than recompiling shaders. Details in
`recon/RENDER_NSXR.md`.

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
