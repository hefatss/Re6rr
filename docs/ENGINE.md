# Engine core (Phase 3)

The engine is a small freestanding C library. The host gives it memory and
already-inflated bytes; the engine owns the Lua state and the asset parsers.
Nothing in `engine/` reads the dump or touches the Windows API.

## Layout

```
engine/include/r6/r6.h        public API: init, scripts, calls, errors
engine/include/r6/r6_asset.h  XMD / NDWD / NTWD structures and parsers
engine/src/core/              Lua host, engine lifecycle, context bundling
engine/src/assets/            bounds-checked asset parsers
engine/src/host/dllmain.c     Windows host-test entry point only
engine/compat/stdio.h         minimal stdio for freestanding host build
third_party/lua-5.1.5/        stock Lua 5.1.5 sources (COPYRIGHT included)
```

## API

- `r6_engine_init(storage, size, config)` — no allocation inside the core.
  `config.log` receives plain messages; `config.arena` is optional scratch.
- `r6_engine_load_script(name, data, size)` — strips UTF-8 BOM, compiles and
  executes immediately, matching `FUN_140aac140`.
- `r6_engine_load_context(scripts, count)` — ordered bundle for one car/colour/
  course. Stops at the first failure; earlier scripts stay loaded.
- `r6_engine_set_setting_const()` — the only native-provided Lua global,
  recovered from `FUN_140c4db10`.
- `r6_engine_call_vec3_key(name, key, index, out)` and
  `r6_engine_call_vec3_index(name, index, out)` — `getglobal`, push args,
  `lua_pcall(n, LUA_MULTRET)`, read top three results. On any failure `out`
  is zeroed, matching `FUN_1400d20d0`'s error convention.
- `r6_engine_call_number(name, out)` — single scalar result; zero on failure.
- `r6_engine_last_error()` — last message, copied into caller's buffer.

## Host build and tests

The host build works without a CRT or Windows SDK: clang emits a DLL with
`-nostdlib /nodefaultlib`, importing only the game's `lua5.1.dll`.

```
python tools/engine/build_host.py --test --dump D:\Games\W6W-05
python tools/engine/test_engine.py --corpus --dump D:\Games\W6W-05
python tools/engine/contexts.py --car CRC_928GT_Masaki --model PLC_928GT --run
```

Verified on this dump:

| check | result |
|---|---|
| 4,885 data scripts loaded through the C host | 0 errors |
| `GetTirePos("CRC_928GT_Masaki", 0)` vs Python Lua host | (-7.73, 0.016652, 12.400767), identical |
| `ColorMax()` with `LibraryColor.lua` | 250 |
| ordered context bundle | reproduces the same `GetTirePos` |
| missing function / bad chunk | clean rc + zeroed vector, no crash |
| 400 `.tex` files, 1,057 NTWD streams, 3,475 texture headers | C parser matches `tools/assets/ntwd_texture.py` |
| 400 `.mdl` files, 21,799 NDWD groups | C parser matches `tools/assets/ndwd_records.py` |

All NTWD streams in this dump are type 2; the type-1 branch is implemented but
has no corpus coverage here. No cube-map or multi-face texture appears either.

## Android build

`CMakeLists.txt` builds `lua51` from the vendored sources plus `r6core`. There
is no Android NDK/SDK on this machine, so the CMake path is authored but not
yet compiled. The platform layer still to be written must:

1. map `sim:data/...` to asset-manager/dump paths and inflate gzip containers;
2. feed bytes to `r6_engine_load_context` in the order from
   `tools/engine/contexts.py`;
3. implement the JNI surface and rendering (Vulkan) outside the core.

## Gaps

- Recompiler (P1) still lacks indirect calls/host stubs, bounded loops and
  XMM/SIMD; 16/18 sampled functions pass.
- NTWD parser records blob offsets; BC1/BC3/RGBA8 decompression not ported.
- NDWD parser covers headers and groups; vertex layouts and material chains
  stay in the Python recon tools for now.
- Physics/race and game systems (P4/P5) not started.
