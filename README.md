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

Phase 0 (recon). See `docs/RECON.md` for what the dump contains and
`docs/recon/*.json` for the raw reports.

## Tools

    python tools/recon/pe_report.py      # PE headers, imports, .pdata function count, PDB
    python tools/recon/pdata_map.py      # every .pdata function: start/end/size/unwind
    python tools/recon/lua_report.py     # Lua inventory + candidate native API
    python tools/recon/assets_report.py  # extensions, gzip containers, shader samples

Results of phase 0: `docs/RECON.md` (summary) and `docs/recon/LUA_API.md` (binding
candidates called from the game's Lua).

All take `--game PATH` (default `D:\Games\W6W-05`) and write into `docs/recon/`.

## Legal

Not affiliated with Bandai Namco. You need your own legally obtained dump. No
DRM, dongle (HASP) or All.Net service circumvention is part of this project;
online features are out of scope.
