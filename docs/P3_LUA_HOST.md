# Phase 3 — Lua host

## Correction to the P0 binding report

`docs/recon/BINDINGS.md` called the 219 names "native implementations". That
reading is wrong. Ghidra decompilation shows the executable *calling Lua
globals* by name:

- `FUN_1400ffb60` (`docs/recon/ghidra_c/func_1400ffb60.c`):
  `lua_getfield(L, LUA_GLOBALSINDEX, name)`, check `lua_type == LUA_TFUNCTION`,
  push a string key and an integer index, call `FUN_1400ff990(L, 2)`, read the
  top three results with `FUN_1400d20d0` into a `Vec3`, then restore
  `lua_settop`. Caller `FUN_1401018c0` passes `"GetCustomGTWingPos"`.
- `FUN_140100540` does the same inline for `"GetTirePos"`.
- `FUN_1400ffdf0` passes one integer; `FUN_1400ffc60` passes one string.
- `FUN_1400ff990` is `lua_pcall(L, n, LUA_MULTRET, 0)`; any error is logged as
  `CallFunction %s` and reported through an error flag pointer.
- `FUN_1400d20d0` reads stack slots `-3, -2, -1` as three `float`s and marks
  any `nil` as failure.

Only three `luaL_Reg` tables exist in the binary (`name_table_summary.txt`):
27 unknown `@SVWH`-style entries, 12 sound functions at `0x1e1a070`, and 3
more at `0x1640e70`. The 219 names are therefore data-script functions that
the native engine consumes, not C functions the port must write. This makes
the port simpler: load the scripts, then call their globals.

## Native → Lua call protocol to reproduce

| direction | form |
|---|---|
| native → Lua | `getglobal(name)`, push `(string key, int index)` or `(int)` or `(string)`, `pcall(n, LUA_MULTRET)` |
| Lua → native | top three results as `Vec3`; single number/string for scalar calls |
| on error | error flag set, stack restored, default zero value returned |

Examples recovered from the callers: `GetTirePos`, `GetCenterPos`,
`GetHeadLightPos`, `GetTailLampPos`, `GetStroboPos`, `GetStroboRoofPos`,
`GetCustomGTWingPos` all take a car-name string plus a zero-based index.

## Globals the native side must provide

Loading all 4,885 scripts under `data/` with a nil-global hook found one name
that no script defines: `SettingConst`, a table with `Locale`, `Language`,
`Difficult`, `NetworkMode`, `NetworkID`, `ForceFeedBackLevel`, `State`.
`data/setting/setting_default.lua` says it is defined by the program. Its
values come from `FUN_140c4db10`, which registers the `sys::setting` enums
through luabind: `Locale` Japan/Usa/China/Korea/Euro = 0..4, `Language`
Japanese/English = 0/1, `Difficult` VeryEasy..VeryHard = 0..4, `NetworkID_0..7`
= 0..7, `NetworkMode` 0/1 (plus `Disable`/`Enable` aliases),
`ForceFeedBackLevel` Disable/TorqueLevel2/TorqueLevel3 = 0..2, and
`State` Disable/Enable = 0/1.

The other nil reads are an order effect, not missing bindings:
`data/car/tire/script/TireDefine.lua` defines `WHEEL_SCALE_INC_13` …
`WHEEL_SCALE_INC_22` and `TIRE_WIDTH_SCALE_155` … `TIRE_WIDTH_SCALE_355` with
the game's real values, but sorted path order reaches its readers first.
`tools/lua/lua_probe.py` preloads that file (`--no-bootstrap` disables it).
With the preload, all 4,885 scripts load without errors and no global is
missing. `--no-stubs` shows the difference: only `setting_default.lua` fails,
on `SettingConst`, and `missing_globals=1 ['SettingConst']`. All 219 names
from `BINDINGS.md` resolve to Lua functions defined by the data scripts; the
port does not need to implement any of them natively.

## Script context matters

The data scripts reuse global names: loading the whole tree makes the last
car's `CarDataPosList` and last colour library's `ColorMax` win. For example:

- with `getTirePos_CRC_928GT_Masaki.lua` alone:
  `GetTirePos("CRC_928GT_Masaki", 0) = (-7.73, 0.016652, 12.400767)`,
  `ColorMax() = 250` after also loading `LibraryColor.lua`;
- with all scripts loaded: `GetTirePos(...) = (0, 0, 0)`,
  `ColorMax() = 6`.

The engine must load one context at a time (one car position file, one colour
library, one course section set). `tools/lua/lua_probe.py --scripts` does that.
`tools/lua/script_sets.py` indexes which script defines each global: 200 of the
219 names have exactly one defining script, 19 are ambiguous (per-car, per-colour
or per-course variants) and need an explicit context choice.

## Validation

    python tools/lua/lua_probe.py --dump D:\Games\W6W-05
    python tools/lua/lua_probe.py --dump D:\Games\W6W-05 \
      --scripts "D:\Games\W6W-05\data\car\position\pos\getTirePos_CRC_928GT_Masaki.lua" \
      --query GetTirePos CRC_928GT_Masaki 0 --vec3

First command: 4,885 scripts, 0 load errors, 0 missing globals. Second:
`(-7.73, 0.016652, 12.400767)`. `tools/lua/lua_host.py` is the reusable ctypes
wrapper; the Android engine will link Lua 5.1 directly but use the same call
protocol.

## Script load sets from the executable

The `.rdata` path templates in `wmn6r.exe` (exported to gitignored
`docs/recon/exe_paths.txt`) and the loaders that reference them give the real
sets and their order. Ghidra decompilations are in
`docs/recon/ghidra_c/carctx/`:

| subsystem | loader | ordered files |
|---|---|---|
| tire | `FUN_140114b00` | `TireDefine.lua` → `TireModelType_<car>.lua` → `TireAccessor.lua` |
| position | `FUN_1400ff3f0` | `getTirePos_<car>.lua` → `CarHightDown_<model>.lua` (conditional) |
| shader | `FUN_14010b110` | `<model>_ShaderParameter.lua` → `ShaderAccessor.lua` |
| colour | `FUN_1400c8330` | `LibraryColor.lua`, or `<dir>/<car>_DefaultColor.lua`, or `playerCar/<car>_CustomColor.lua` (file type selects one) |
| spec | `FUN_140103a90`/`FUN_140103b90` | `<model>_Specification.lua` |

The strings carry a `sim:` prefix: that is the game's virtual filesystem,
mapped to `data/` on disk. Car name and model code are different namespaces:
`CRC_928GT_Masaki` pairs with `PLC_928GT`. `tools/engine/contexts.py` builds
these bundles in order and can load them through the C engine.

LuabindPack::Load (`FUN_140aac140`) strips a UTF-8 BOM, calls
`luaL_loadbuffer`, then runs the chunk with `FUN_140aad540(L, 0, -1, 0)` — a
load is always execute-immediately, so no separate deferred chunk queue is
needed.

## Next

1. ~~Determine script load sets and order from the engine's script loader.~~
   Recovered above; `tools/engine/contexts.py` applies them.
2. ~~Port the `Vec3`/scalar helpers and error-flag convention to the engine
   side.~~ Done in `engine/src/core/lua_host.c`; failed calls return zero.
3. ~~Wire car position/colour to the Phase 2 loaders.~~ `r6_engine_load_context`
   and the first asset parsers are in `engine/`; see `docs/ENGINE.md`.
4. Extend recompiler gaps: indirect calls/host stubs, bounded loops, XMM/SIMD.
5. Proceed to P4 physics/race and P5 game systems.
