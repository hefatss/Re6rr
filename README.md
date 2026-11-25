# Re6rr

A native port of *Wangan Midnight Maximum Tune 6RR* (Namco System ES3, x86-64,
Windows Embedded) for Android, in the spirit of
[super3dxplus](https://github.com/…) but a separate code base: 6RR is a different
engine (Enma, DirectX 11, Lua 5.1 driven) and a different executable
architecture, so nothing about its assets or its game code can be reused from
the 3DX+ port beyond ideas.

This repository contains **no game content**. It only holds tools that read a
dump you own (`wmn6r.exe`, `data/`, `data_jp/`) and code that runs the result.

## Status

Status legend: **Done** = implemented and checked against shipped data;
**Partial** = working subset, gaps listed; **Open** = not implemented;
**Out of scope** = deliberately excluded.

| Area | Status | Keterangan |
| --- | --- | --- |
| P0 recon | Done | PE/imports/`.pdata`, Lua inventory, 219 native bindings, Ghidra full analysis of `wmn6r.exe` and `nuSound2_win64.dll`. |
| P1 x64 → C lift spike | Done | IR lift, annotated disassembly, C emit, Unicorn difftest against original bytes. |
| P2 asset decode | Done | gzip/NTWD containers, NDWD → OBJ, 223 `.nsh` / 446 DXBC blobs decoded, 149 `.nub` banks and 781 tones read. |
| P3 engine core + Lua | Done | Freestanding C core, stock Lua 5.1.5 host, script contexts, asset parsers; full corpus check. |
| P4 physics / course / race | Done | Vehicle dynamics from shipped Lua spec and tire positions, road polyline projection, race rules, rivals, `EPlayState` values. |
| P5 game flow + `SConfigPlay` | Done | Freestanding state machine and recovered byte bridge. |
| P5 catalogs | Done | 151 cars, 77 mappings, 250 colours, 107 wheels, 261 aero/parts, 151 tunes, 42 tire scales. |
| P5 story data | Partial | 122 episodes, 3,309 messages, 3,484 events, 647 `drive_story_*` keys extracted; native condition schema known, per-episode predicate instances absent from dump. |
| Audio tables + dispatch | Done | 142 BGM ids, 12 Lua bindings, `config.bin`/`config_3d.bin` layouts, Sound::Initialize config/Impl ABI, `KeyOn` defaults, positional SE stride, 64 bank/voice slots, BGM stream handle; stage-effect symbols resolved to bank 3 tones `0xe`/`0xf`. |
| Audio playback internals | Partial | Mixer bus/fade ABI, dB↔volume conversion, 0xa0 voice-request layout and extended-KeyOn activation via 3D vectors recovered; envelope semantics and playback host unresolved. |
| Scene data (`.EES`) | Partial | 1,129 containers parsed; camera fields through `+0x10c` named, `CAMID` → `CamData.EES` slot bridge proven; `car_effect` copy ABI mapped, field semantics and remaining camera bytes uninterpreted. |
| Renderer | Partial | Shipped SM4 DXBC operands and structured IF/LOOP/SWITCH blocks decoded; no GLSL/Vulkan translation and no renderer host. |
| Android host | Partial | C core + JNI and Java bridge syntax-checked; NDK/SDK absent, no APK built. |
| Test suite | Done | `build_host.py --test` plus all `test_*.py` green against the dump. |
| Online / DRM | Out of scope | No dongle (HASP) or All.Net circumvention. |

Details in `docs/P1_STATUS.md`, `docs/ASSETS_NOTES.md`, `docs/P3_LUA_HOST.md`,
`docs/P4_PHYSICS.md`, `docs/P4_COURSE_RACE.md`, `docs/P5_GAME.md`,
`docs/P5_CARS.md`, `docs/P5_STORY.md`, `docs/P5_CUSTOM.md`,
`docs/ANDROID_HOST.md`, `docs/ENGINE.md` and `docs/RECON.md`. Raw reports go to
`docs/recon/*.json` (gitignored).

## Tools

    python tools/recon/pe_report.py      # PE headers, imports, .pdata function count, PDB
    python tools/recon/pdata_map.py      # every .pdata function: start/end/size/unwind
    python tools/recon/lua_report.py     # Lua inventory + candidate native API
    python tools/recon/assets_report.py  # extensions, gzip containers, shader samples
    python tools/assets/dump_asset.py FILE [--limit N]   # hexdump a container payload
    python tools/assets/xmd_streams.py FILE              # cluster XMD.001 streams by tag
    python tools/assets/ndwd_mesh.py FILE --stream 0 --out out.obj  # NDWD -> OBJ
    python tools/x64/string_xref.py      # name strings -> containing functions
    python tools/x64/name_table.py       # name pointer tables / luaL_Reg records
    python tools/x64/bindings.py         # merged BINDINGS.md (all 219 Lua API names)
    python tools/x64/func_disasm.py f_8555   # annotated disassembly
    python tools/x64/difftest.py --seeds 30  # original bytes vs lifted IR (Unicorn)
    python tools/x64/emit_c.py f_8555     # C output from the same IR
    python tools/lua/lua_probe.py --dump D:\Games\W6W-05  # load data scripts
    python tools/lua/lua_probe.py --scripts PATH --query GetTirePos NAME 0 --vec3
    python tools/lua/script_sets.py --name GetTirePos  # which script defines a global
    python tools/engine/contexts.py --car CRC_928GT_Masaki --model PLC_928GT --run
    python tools/recon/enma_api.py --dump D:\Games\W6W-05  # Enma exports/enums/layouts
    python tools/recon/enma_sim.py --dump D:\Games\W6W-05  # CGameInput offsets
    python tools/engine/build_host.py --test           # build C core + JNI checks
    python tools/engine/test_engine.py --corpus        # all data scripts via C
    python tools/engine/test_physics.py               # vehicle dynamics checks
    python tools/engine/test_race.py                  # course projection + race rules
    python tools/engine/test_game.py                  # game flow + SConfigPlay bytes
    python tools/engine/car_catalog.py --list          # 151 car specs
    python tools/engine/car_mapping.py               # CRC_* -> PLC_* pairs
    python tools/engine/test_catalog.py               # packed catalog parser
    python tools/engine/course_descriptor.py --list-routes
    python tools/engine/course_descriptor.py --route FUKUOKA --out out.r6course
    python tools/engine/course_surface.py --area FUKUOKA --section 101

Ghidra headless (needs `GHIDRA_INSTALL_DIR` set to a 12.1+ install):

    analyzeHeadless <proj> wmn6r -import <exe> \
      -scriptPath tools/ghidra -preScript DisableHeavyAnalyzers.java
    analyzeHeadless <proj> wmn6r -process wmn6r.exe -noanalysis \
      -scriptPath tools/ghidra -postScript ExportDecomp.java <out> <list>

Recon tools take `--game PATH` (default `D:\Games\W6W-05`). x64 tools take
`--exe PATH` (default `D:\Games\W6W-05\wmn6r.exe`). Most write into
`docs/recon/`, which is gitignored.

## Legal

Not affiliated with Bandai Namco. You need your own legally obtained dump. No
DRM, dongle (HASP) or All.Net service circumvention is part of this project;
online features are out of scope.
