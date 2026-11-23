# super6rr

A native port of *Wangan Midnight Maximum Tune 6RR* (Namco System ES3, x86-64,
Windows Embedded) for Android, in the spirit of
[super3dxplus](https://github.com/…) but a separate code base: 6RR is a different
engine (Enma, DirectX 11, Lua 5.1 driven) and a different executable
architecture, so nothing about its assets or its game code can be reused from
the 3DX+ port beyond ideas.

This repository contains **no game content**. It only holds tools that read a
dump you own (`wmn6r.exe`, `data/`, `data_jp/`) and code that runs the result.

## Status

Phases 0–2 done (recon, x64 → C lift spike, asset containers). Phase 3 in
progress: see `docs/P1_STATUS.md`, `docs/ASSETS_NOTES.md` and
`docs/P3_LUA_HOST.md`. Raw reports go to `docs/recon/*.json` (gitignored).

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
