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
| `.reloc` | **1,833** blocks / **270,128** entries (825 type 0, 269,303 type 10); `tools/engine/reloc_inventory_catalog.py` copies page/section facts without applying fixups |
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
| `.lua` | 4,885 | 154 MB | plain text, mostly data tables (car spec/colour/position/vinyl, course clip lists); `tools/engine/shader_param_catalog.py` inventories 142 `car/shader/parameter/*_ShaderParameter.lua` files with 8 float32 values each |
| `.bin` | 1,495 | 2.80 GB | raw float32 course geometry (some gzip); `tools/engine/course_paths_catalog.py` inventories 178 `data/course/path` bins |
| `.nut` | 580 + 10,571 | 1.18 GB + 1.94 GB | gzip, inner `NTWD` (model/scene) |
| `.tex` | 1,175 + 75 | 406 MB | gzip/raw `XMD.001`; `tools/engine/xmd_asset_catalog.py` inventories headers and streams |
| `.mdl` | 578 + 32 | 188 MB | gzip `XMD.001`; `tools/engine/xmd_asset_catalog.py` inventories headers and streams |
| `.nub` | 149 | 3.45 GB | raw sound banks (`data/sound/BGM...`) |
| `.ees` | 1,129 | 2.89 GB | raw `EventScene2` header + typed arrays — scene camera/car data |
| `.nud` | 371 | 6.2 MB | `NDWD` — navimap |
| `.nsh` | 257 | 1.4 MB | `NSXR` — compiled shader blobs |
| `.act` | 170 | 6.8 MB | `RESOURCE:NU` — effect actors |
| `.lmd` | 985 | 13 MB | gzip → `XMD.001` — flash UI; gzip/XMD headers and stream sizes are inventoried by `tools/engine/lmd_catalog.py` |
| `.xmlt` | 591 | 1.0 MB | XML text (story lines, cut-in tables); `tools/engine/xmlt_lists_catalog.py` inventories 3,482 lists, 4,432 seeds and 16,544 field tags without copying text values |
| `.nuf` | 22 | 0.7 MB | `NUF`/`NFH` — fonts; `tools/engine/nuf_headers_catalog.py` inventories paths, sizes and first 64 bytes |
| `.mtmp` | 34 | 28.9 KB | `SCALE:` + `OBJECT:` text tables; `tools/engine/mtmp_catalog.py` copies 286 raw object lines |
| `.med` | 28 + 39 | 3.9 MB | motion data |
| `.gz` | 1,087 | 36.8 MB | stage effects; `tools/engine/gz_effect_catalog.py` verifies CRC/ISIZE and inventories gzip headers plus 16-byte inflated prefixes |

The 20 root `FBK_W6W_*.bin` / `GBK_W6W_*.bin` files are gzip banks with 22
`WMBK` records total; each F/G pair inflates byte-identically.
`tools/engine/wmbk_bank_catalog.py` copies gzip header words, record headers
and byte spans, but does not decode record payload words.

The 9 `data/ghost/default_ghost_*.bin` tables hold 69,056 records at stride
136; `tools/engine/default_ghost_catalog.py` copies paths, counts, code words
and NUL-terminated name-length ranges, but no ghost names, ids or trajectory
values.

All 170 `.act` files start with `RESOURCE:NU`; their paths, sizes and first 64
bytes are inventoried by `tools/engine/act_headers_catalog.py`, but no section
or animation semantics are inferred. The 67 `.med` files all have zero bytes
through `0xff` and eight u32 words at `0x100` encoding frame count, three
section sizes, two derived byte counts and total file size;
`tools/engine/med_headers_catalog.py` validates and packs those headers, but no
frame or animation data is interpreted.

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
1 stream. Its ctor writes a 0x28-byte config at `0x1407d674d`: counts at `+0`
(`<=0x10`), `+4` (`<=0x100`), `+8` (`1..0x10`), config pointers at `+0x10` and
`+0x18`, and an opaque `bnusCoreInitEx` argument at `+0x20`. `sys::Sound::Initialize`
(`0x140c53c20`) passes it to the 0x98-byte Impl ctor (`0x140c533c0`), whose
vectors sit at `+0`/`+0x20`/`+0x40` with strides `0x20`/`8`/`0x10`; each stream
gets a `0xac440` buffer and output mode is fixed at 4. `nuSound2_win64.dll`
analysis also recovers 64 bank slots of stride
`0x804` and tone-record `+0x28` bit 0 as the loop flag. `sys::Sound::Impl::playSe`
uses a 0x20-stride bank table with the nuSound2 handle at bank `+0x18` and calls
`nuSound2KeyOnHandle(handle, tone, 0)`. Twelve Lua sound bindings were recovered
from the `luaL_Reg` table at `0x141e1a070`: `PlaySE` fixes bank 2 (SYSTEM),
`PlaySEOfBank` takes the bank, and Decide/Cancel/Move hardcode tones `0x2f`
(`SELECT`), `7` (`CANCEL`) and `0xf` (`CURSOR`). BGM ids `0..141` map through a
142-entry name table (`0x1414ec550`, 0x40-byte strings) and a 142-pointer path
table (`0x141e1f8e0`); id `0x8c` stops and `0x8d` is the rejected `RANDOM` id.
`FUN_1407d6940` keeps the current and queued BGM ids at SoundManager `+0x44c`
and `+0x450`: `-1` is a no-op, an id when none plays starts stream 0, a
different id is queued after a fade, and the same id logs "play already".
The Lua `FadeOutBGM` binding (`0x140781ba0`) takes 60 fps frame counters and
passes `((max_frame-now_frame)/60)*1000` milliseconds to `FUN_1407d48c0`, which
calls `nuSound2StreamFadeOut(handle 0, ms)`. In nuSound2 (`FUN_180016850`) an
idle stream returns `0x8000000b`, a playing stream starts fade mode 2 with
frames `ms/5.333` and step `-volume/frames`, and a stream already fading returns
`0x80000000`; other states stop immediately via `FUN_1800161e0`.
A second `playSe` entry point calls `nuSound2KeySetOnHandle(handle, tone,
volume, pan, flags, &key)`; `readyBank` requires bank state `3` at `+0x1c`.
`playSeLoop` uses 8-byte request records and scene sound reserves slot `0x21`
of 34; `nuSound2KeyOnHandle` defaults are volume `1.0`, pan `0.0`, flags `0`.
`FUN_1401aebc0` drives positional SE from 0x24-byte records
(bank, tone, interval, xyz); `FUN_140c50d80` (`play3DSeLoop`) takes two xyz
triples and enters the same 0xa0 voice request through
`nuSound2_3DKeySetOnHandle` with request id 0. Playback ABI: BGM goes through
`nuSound2StreamStartEx(handle 0, path, 0)`; `nuSound2_win64` keeps 64 voice
slots of 0xa0 bytes with metadata at `0x2800 + slot*0xc`, while bank setup at
`FUN_18002eb80` uses 0x804-byte slots and returns distinct errors for bad index,
bad format, null data, already-set banks and voice/stream failures.
`nuSound2BankRegister` (`0x180299c0`) forwards to `0x18002f370` and `0x18002f1c0`,
which claims the first slot with a null pointer at `slot*0x804+0x42`; setup then
checks version bytes `0..2` as `1,2,1`, tone count at `+0xc`, data offset/size at
`+0x10/+0x14`, and an offset table at `+0x18` whose base is `0x20`. Each tone
record stores length/data offset/format count at `+0x14/+0x18/+0x1c`, and the WAV
format block begins at `+0xbc`; `FUN_180035b80` reserves the data size at
instance `+0x80508` under a `0x20000000` cap. Cleanup (`0x18002e7d0`) reads the
same slot records at `0x108 + slot*0x2010` and releases each voice id.
`audio_events.bank_setup_view()` mirrors those native reads; all 149 shipped
banks match the independently parsed header/tone records (781 tones).
Tone records also carry playback control fields: `+0x44`/`+0x50` and `+0x54`
feed `nuSound2_3DGetParameterChNum`, `+0x58`/`+0x5c` cap requested volume and
pan at `1.0` in all 781 tones, `+0x60` selects a bus chain read by
`FUN_18001cd90` (ids `0,1,2,4,5` in the dump), and `+0x68` supplies the chain
record's voice-bus id (zero throughout). `nub_audio.tone_control()` reports
these fields without storing audio bytes.
Chained KeyOn (`0x180026a60`) builds up to 32 voices; `0x180025b80` fills a
52-float state record at instance `0x21c + index*0xd0`, and `0x180029220`
applies it to the core voice: volume and FX volume clamped to `0..1`, pitch
`2^(cents/1200)`, two filter parameters, a 6x6 speaker-volume matrix and 3D
mode/channel/bus/bank/tone/voice ids. Core voice ids come from a 192-entry
table at instance `+0x44` with stride `0x178`. These are runtime records, not
shipped data; attack/decay envelope fields remain unproven.
`config_3d.bin` is parsed by `nuSound2_3DSetConfig`: version bytes `1,2,3`,
5 sections of `0x130` bytes, each with ten `0x1c`-byte records and six trailing
dwords; record dB fields convert to amplitude with `10^(db/20)`.
Mixer ABI: 68 buses of 0x48 bytes with fade target/step/frames fields, plus
piecewise-linear dB ↔ volume conversion calibrated at instance
`+0x1c20/+0x1c28/+0x1c2c`. The 0xa0 voice request layout is known from
`FUN_1800237d0`: request/bank/tone, three pointers, volume/pan/flags and six
floats with defaults from `FUN_1800011b0`. `FUN_18001a4e0` is `memcpy`;
`FUN_180026a60` activates the extended path only when both extension pointers
are non-null, and `FUN_1800237d0` copies `0x34` bytes to request `+0x34` and
`0x1c` bytes to `+0x68`. The six-argument game wrappers pass null pointers;
`play3DSeLoop` (`0x140c50d80`) is the only game xref to the
`nuSound2_3DKeySetOnHandle` import thunk (`0x140dee20a`): it supplies an internal
position at `Sound::Impl +0x60`, copies two 12-byte caller vectors and a chgrp
scalar into one `0x1c`-byte block, and passes the voice-slot output with it. The
DLL wrapper copies the same two vectors and chgrp into a contiguous block before
calling `0x180029cc0`, so the `0x34`-byte blob starts at that block and the
`0x1c`-byte blob starts at the voice-key record. Plain
`nuSound2KeySetOnHandle`/`KeyOnHandle` and their ID variants reach
`FUN_180029e00`/`0x18002a490` with null extension pointers. Point 3D wrappers
(`0x1800363b0`, `0x1800361f0`, `0x180036900`, `0x180036740`) pass a three-float
position pointer plus a 12-byte vector copy through `0x180029cc0`/`0x180029eb0`;
line variants (`0x1800365e0`, `0x180036a10`) first derive a four-float position
with `nuSound2_3DLineGetPosition` (`0x180034e70`). No exported envelope API
exists; the extended blob bytes remain 3D vector plumbing, not proven envelope
stages. `tools/engine/audio_events.py` reads
these tables, models the mixer and voice request, and checks the dispatch ABI. No shipped Lua file calls any sound binding, but
three stage-effect parameter files declare symbolic `NUD_TONE_RACE_HANABI1/2`
names; those resolve to RACE bank 3, tones `0xe`/`0xf` and match the literals in
`FUN_1401b0cd0`. All other event → `(bank, tone)` pairs remain native
call-site constants. Format details, call sites and the remaining envelope
gaps (the two copied extension blobs) are in `recon/AUDIO_NUB.md`.

`.EES` scene files are raw, with no encryption or decompression on the native
load path. Two camera variants (`0x2712`/`0x2713`) hold 255 records of `0x50`
plus `0x160` bytes; car files hold 10,800 records of `0x180`, `0xa0` and `0x8c`
bytes. All 1,129 shipped files parse with exact size identity;
`tools/engine/ees_scene.py` inventories and extracts the arrays, and
`tools/engine/ees_inventory_catalog.py` packs the 1129 header facts and 2667
array records for the bounded C reader. Native
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

`.nut` files are gzip-wrapped or raw texture containers: 5,577 raw NTWD,
5,431 gzip NTWD and 143 gzip NTLX. NTWD stores version/entry counts at `+4`,
per-entry payload size at `+0x18`, descriptor size, packed dimension fields at
`+0x20`/`+0x24` and the first GIDX offset at `+0x30`; a `0x10` prefix and
one descriptor per entry precede the payloads, with descriptor size from `+0x1c`
(`0x50`, `0x60`, `0x70` or `0x80`). All 36 `sp_cutin` files are 384x320,
one entry, `0x1e000` payload bytes at `+0x60`. NTLX uses version 1, always
gzip-wrapped, with the same prefix/descriptor layout, descriptor size `0x50`,
GIDX offset zero at `+0x30`, and payload bytes per pixel of either 1 or 4; 140
of 143 files match the exact layout. Pixel-format semantics are not inferred.
`tools/engine/nut_texture.py` inventories the corpus without storing texture
data. `tools/engine/nut_file_catalog.py` packs all 11,151 file-level headers
into `.r6ntf`; no payload or pixel bytes are copied.

Shader folder holds compiled DXBC blobs inside `NSXR`, not HLSL source, so a
port translates behaviour rather than recompiling shaders. SM4 control flow is
structured: 272 `SWITCH`, 22 `LOOP` and 9 `IF` blocks match cleanly across all
446 blobs with no label operands or unmatched closers;
`nsxr_shader.control_flow()` builds the nested block map. `uniform_usage()`
resolves cbuffer operands to named RDEF variables by byte offset: 5,502 static
operands map across all 446 blobs, 8 use dynamic indices and none are unresolved.
`resource_usage()` maps 680 texture and 680 sampler operands to RDEF resource
names; all 1,052 declarations and uses match a reflection binding. The 43 SM4
opcodes in the corpus are classified for a GLES ES 3.00 backend: 11,184 direct
instructions, 2,720 needing a small rewrite (`MAD`, `EXP`, `LOG`, `MOVC`),
5,979 control-flow instructions following the decoded blocks and 680 `SAMPLE`
instructions using RDEF bindings. `glsl_es_source()` emits GLSL ES 3.00 for
all 446 records: #version/precision, ISGN/OSGN locations, float temps plus
`ivec4` shadows for integer components, `vec4 xN[]` indexable temp arrays,
RDEF-named std140 UBO members for static cbuffer accesses (442 records),
named uniform arrays for the 4 relative-index records, sampler uniforms,
structured `switch`/`for`/`if`, float comparison masks, integer ops and
relative cbuffer/array indices. SM4 registers
are typeless: writes to one shadow mirror into the other through
`floatBitsToInt`/`intBitsToFloat`. `MOVC` follows the documented SM4 order
`dest, src0, src1, src2`: any bit set in `src0` selects `src1`, otherwise
`src2` (Microsoft SM4 assembly reference, `movc (sm4 - asm)`).
`nsxr_shader.py --glsl Copy.nsh --stage 1` prints one example;
`--glsl-dir DIR` writes all 446 files plus a SHA-256 manifest. The manifest
also carries the host-facing interface for each stage: 1,590 inputs, 1,457
outputs, 797 cbuffers with 2,029 reflected std140 member offsets, 526 samplers
and the UBO/array-mode flag. `glsl_ubo.py` and `r6_glsl_pack_ubo()` pack scalar, vec4 and mat4 values into
those reflected offsets; sampler binding and GPU upload are still open. Details in `recon/RENDER_NSXR.md`.

- `AMCUS/AMUpdaterData/Graphics` has 8 TGA files: 4 type-2 exact-size images
  and 4 type-10 RLE images, all with the 26-byte `TRUEVISION-XFILE.` footer.
  `tga_inventory_catalog.py` copies headers and sizes but no pixel bytes.
- `data/course/street_lamp` has 168 `LAMP_*.bin` files with 24,916 stride-28
  records and 697,648 bytes. `street_lamp_catalog.py` copies paths, strides,
  counts and u32 flag ranges but no coordinate floats.
- `data/effect/stage_effect` has 757 `PCV_*.bin` files with 19,551 stride-12
  float triples and 234,612 bytes. `pcv_inventory_catalog.py` copies paths and
  triple counts but no float bit patterns or effect semantics.

## Lua

- 4,885 scripts in `data`, 167 in `data_jp`; text, no `require` usage, no bytecode.
- Content is data: car specification (151 files), car positions (255), colours,
  vinyl/sticker tables, course clip lists (`course/stage/*/clip`), plus settings.
- 812 names defined in Lua itself; real flow logic stays in the executable.
- `data/Enma` has 6 `ytErrorLogMerge*.txt` tables, 4,010 CRLF lines;
  `tools/engine/enma_error_log_catalog.py` copies layout facts but no numeric
  log values.
- `data_jp/filter` has 17 Lua files; `tools/engine/filter_dictionary_catalog.py`
  copies line kinds, byte spans and true/false tokens but no dictionary words.
- `data_jp/menu/Zenichi/ZenichiConfig.lua` is 30,209 bytes; its
  `NAME_PLATE_INFO` table has 276 contiguous rows with ids 1..276, variation
  1..6, layout 0..1 and 273 distinct texture names. `zenichi_config_catalog.py`
  copies those facts but no title/reward behaviour.
- `data_jp/platform_parameters/lua/ghost_expedition_sugoroku.lua` is 19,910
  bytes; `ItemTable` has 6 categories and 115 item ids, `SquareTable` has 7
  stages, 14 pages, 361 squares, 7 square tokens and 6 reward categories.
  `sugoroku_board_catalog.py` copies aggregate counts and function names but
  not per-square selections or dice/reward rules.
- `data_jp/menu/menuTex/Customframe/Customframe.lua` is 26,386 bytes; its
  `CUSTOM_FRAME_INFO` table has 183 contiguous ids and 732 unique 21-character
  `cmn_cf_*.nut` names with six accessor functions. `custom_frame_catalog.py`
  copies those names but no frame behaviour or texture payload.
- `data/motion/introduction/IntroductoryMotions.lua` is 2,443 bytes;
  `MOTION_FILES` has DEFAULT and ZENICHI rows of two `.MED` names plus waits
  20/60, two zero frame scalars and six accessors. `introductory_motions_catalog.py`
  copies those facts but no `.MED` payload or animation semantics.
- 219 identifiers called from Lua that exist as strings in the executable — the
  candidate native binding surface (top: `GetShaderCarVec4/Float/Int`, `GetTirePos`,
  `GetCenterPos`, `GetCustomGTWingPos`, `GetCarHightDown`, `GetCarAeroTireOffset`,
  `GetGTWing*`, `IsVinylSelectOriginal`, `getVinylColor`, `getMiniStickerColor`,
  `ColorMax`, course queries `GetAreaId`, `GetCameraDirection`, `GetPathList`,
  `GetRelatedSection`, `HideClip_*`, `DistClip_*`, effect queries `GetAura_*`,
  `GetAfterFire_*`). Full list in `lua_api.txt`.
- Extraction needed a CP932 fallback; the first pass (UTF-8 only) produced noise.

`hints.dat` is 1,072 bytes: 67 stride-16 records with 61 distinct rows and a
zero byte at offset 15 of every record. `hints_catalog.py` copies the opaque
words without decoding names or meanings.

Five `data/course/parameter/relation/RelatedSection*.lua` files total 66,205
bytes and contain 540 pairs of fixed six-integer arrays, all values at most 604,
with `LOAD_SPEED = {5, 5}` in each file. `related_section_catalog.py` copies the
paths, sizes and raw arrays without assigning section semantics.

`EVENT_SCENE_HIDECLIP_ENDING.lua` is 250 bytes and lists four ASCII model names;
`EventSceneAccessor.lua` is 553 bytes and defines
`EventSceneHideClip_GetHideModel()` using `unpack`. The catalog copies the names
and accessor name only, with no scene timing or visibility semantics.

Twenty-three `data/course/debug/DEBUG_TDB_A_*.lua` files total 603,341 bytes
and contain 12,087 rows of `"0xHHHHHHHH", "ASCII_NAME", -- decimal`, where the
decimal always equals the hexadecimal id. `DEBUG_BLINK_NUDS_LIST.lua` has four
ASCII model names and `DebugAccessor.lua` defines ten `GetDebug*` functions.
The catalog copies paths, ids, comments, names and function names without
rendering or gameplay meaning.

Seventy `data_jp/scene/**/Scene.Lua` files total 8,629 bytes and each has the
same five-line shape: `S_DATA_ROOT`, `S_ENVIRONMENT_DATA =
"/Environment.Lua"`, `I_EVENT_NUM = 0` and an empty `S_EVENT` table. The catalog
copies those strings and counts without camera or scene semantics.

Six `data/effect/stage_effect/**/parameter/filename.txt` files total 1,023
bytes. Each begins with the literal `filename.txt` and then lists 4 to 8 ASCII
`.lua` basenames, 34 in total. `stage_effect_filename_lists_catalog.py` copies
the paths and names only, with no effect behavior.

`data/Enma/ytConfigStorySeries.txt` is 28,433 bytes and 1,511 lines. It has 125
`ESeries_*` block headers and 1,249 token lines before `//` comments.
`story_series_tokens_catalog.py` copies the headers and token text verbatim
without deriving race, story or carryover rules.

Six root `*setting.lua.gz` files total 2,882 compressed bytes and inflate to
7,258 ASCII bytes. Each has the same gzip envelope format and 60 lines: a
three-line header, a blank line, 53 `NAME = INTEGER` rows and a three-line
footer. `setting_lua_gz_catalog.py` copies paths, gzip words, key names and
integer literals only; deflate payloads and setting meanings are not inferred.

Six `HIDECLIP_*.lua` files under
`data/course/stage/A_TOKYO_NGT_EXT/WANGAN/clip` total 140,107 bytes and 2,994
lines. Each has a timestamp comment, one `HIDE_MODEL_NN = {` table and a
closing brace; the filename suffix matches the table id. The catalog copies
paths, sizes, timestamps and 2,972 ASCII model names without clip timing,
render state or geometry.

`data/course/parameter/navimap/NavimapParam.lua` is 1,137 bytes and 32 CRLF
lines. It has four ASCII scalar rows (two active, two commented) and eleven
`0/1/2` rows in `NAVIMAP_USE`. `navimap_param_catalog.py` copies the path,
global names and integer literals; Shift-JIS comments and navimap behavior stay
unparsed.

Three hundred `data/effect/**/parameter/SET_*.lua` files total 501,917 bytes
and 1,899 `path`/`model` rows. Each has one set name, one `num`, one
`EffectSetNum` and a fixed row shape with float, transform and timing fields.
`effect_set_inventory_catalog.py` copies paths, set names, integer tokens and
path/model strings only.

`FFBPlugin.ini` and `BanaConfig.ini` total 1,039 bytes and 46 CRLF lines.
They hold two `[Section]` names, 41 `Key=value` pairs and 3 `;` comment lines.
`root_ini_catalog.py` copies section names, keys, values and comments; device,
card and online behavior stays unparsed.

395 `data/course/stage/**/clip/DISTCLIP_*.lua` files total 83,284 bytes
and 3,950 active integer rows. Every file has one table global
(`DEFAULT_CLIP_DISTANCE` or `CLIP_DISTANCE_00`..`07`) and ten rows drawn
from a fixed ten-key vocabulary. `distclip_catalog.py` copies paths,
table names, keys and integers; comment lines and clip rendering are
not parsed.

`data/course/parameter/tuning/RampParam.lua` and `TAParam.lua` total
5,267 bytes and 101 CRLF lines. They hold 39 two-integer ramp rows
and 25 one-integer TA rows with copied ASCII `GID_*`, `ERamp_*` and
`EStage_TA_*` labels. `course_tuning_catalog.py` copies integers and
ASCII labels; CP932 header comments and tuning behavior stay unparsed.

Three `XMD\0001\0` containers outside the `.TEX`/`.MDL` family total
527,072 bytes and 30 streams: two flash files with version 1 and
three streams, plus `honor.bin` with version 0 and 24 streams.
`xmd_v1_directory_catalog.py` copies paths, sizes, offset tables
and eight magic bytes per stream; payloads stay unparsed.

`data/car/position/StroboLightOnOffParameter.lua` is 3,771 bytes
and 95 LF lines. It has `DEBUG_CODE = 0`, two integer-pair tables
with 5 and 3 rows, and four accessor definitions.
`strobo_parameter_catalog.py` copies those integers and ASCII
names; CP932 comments and timing/rendering behavior stay unparsed.

Three `data_jp/scene/func/Func_*.Lua` files total 4,289 bytes and
223 CRLF lines. They define 43 functions with copied ASCII return
expressions. `scene_func_catalog.py` copies paths, names and return
expressions; CP932 comments and scene logic stay unparsed.

240 `data/car/tire/model_type/TireModelType_*.lua` files total
165,906 bytes and 7,201 CRLF lines. Each has 8 fixed sections:
4 `inc_normal` and 4 `inc_size_up` TIRE names, 4 wheel-scale and
4 tire-width tokens, one `wheel_default` and one `wheel_color`.
`tire_model_catalog.py` copies the names, tokens, defaults and
colors; two float fields and CP932 comments stay unparsed.

`data/Enma/ytConfigStoryRival.txt` is 145,966 bytes and 5,261
LF lines. It defines 398 `ECharacter_*` blocks with 201 unique
names and five keyword rows each. `rival_block_catalog.py` copies
names, line spans, ASCII keyword rows and counts; CP932 comments,
float fields and rival behavior stay unparsed.

`data/setting/setting_default.lua` is 1,343 bytes and 34 LF
lines. It has 13 `m_*` rows: 12 active and one commented locale
row, with 8 `SettingConst` tokens and 5 hex literals.
`setting_default_catalog.py` copies names, flags and value tokens;
Japanese comments and setting behavior stay unparsed.

Two `data/etc/ntp.*.conf` files total 1,425 bytes and 61 LF lines.
They hold 23 active directives, 22 comment lines and 16 blanks.
`ntp_config_catalog.py` copies paths and verbatim ASCII lines;
time-service behavior stays unparsed.

Seven shipped `AreaAccessor.lua`, `ParamAccessor.lua`,
`SectionAccessor.lua`, `StageAccessor.lua`, `ShaderAccessor.lua`,
`TireAccessor.lua` and `EffectSetTool.lua` scripts total 35,256
bytes and 1,290 LF lines. They define 155 top-level functions.
`accessor_script_catalog.py` copies paths, names, argument lists,
first return expressions and line positions; CP932 comments,
`unpack()` semantics and render/tuning behavior stay unparsed.

`data/Enma/ytCarryover.txt` is 398 bytes and 10 CRLF lines: one
series token, five scalar lines and four fixed data rows.
`carryover_catalog.py` copies tokens verbatim; carryover rules,
checkpoint tokens, coordinates and float semantics stay unparsed.

`data_jp/car/specification/PLC_MA61_Specification.lua` is 139,729
bytes and 3,000 CRLF lines. `CarDataList` spans lines 12–387 with
373 scalar rows: 317 integers, 2 floats, 38 ASCII strings and 16
non-ASCII literals. `spec_ma61_catalog.py` copies keys, ASCII
literals and comment flags; Japanese literals/comments and tuning
meaning stay unparsed.

`gamecontrollerdb.txt` is 506,637 bytes and 1,916 CRLF lines: 7
comments, 5 blanks and 1,904 active rows. `sdl_db_catalog.py` copies
verbatim ASCII/tab lines, id/name/platform spans and field counts;
SDL button meaning and remap behavior stay unparsed.

`keyconfig.toml` is 1,106 bytes and 39 CRLF lines: 22 active
rows, 13 comments and 4 blanks. `keyconfig_toml_catalog.py`
copies verbatim lines and kinds; key binding meaning and SDL
token resolution stay unparsed.

`card.ini` and `teknoparrot.ini` are 63 and 715 bytes with 3 and
36 lines. `root_ini_keys_catalog.py` copies section names, key
names, line positions, value-presence flags and section indices;
raw values, including identifiers, stay uncopied.

`data/car/color/NeonColor.lua` is 1,180 bytes and 31 CRLF lines.
`neon_color_catalog.py` copies the six row positions and 18
verbatim numeric token bytes; CP932 comment text, index order and
fallback behavior stay unparsed.

`data/Enma/ytPhantomTempRun.bin` is 18,728 bytes: 6 header words,
5 u64 timestamps and 2,333 u64 records. `phantom_run_catalog.py`
copies the words verbatim; timestamp units, record flags and
sample encodings stay unparsed.

Three AMCUS INI files total 5,139 bytes and 204 CRLF lines:
`AMConfig.ini`, `AMConfig.ini.orig` and `WritableConfig.ini`.
`amcus_ini_keys_catalog.py` copies section/key names, line kinds,
positions, value-presence flags and section indices; values and
CP932 comments stay uncopied.

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
