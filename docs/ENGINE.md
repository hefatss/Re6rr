# Engine core (Phases 3–5)

The engine is a small freestanding C library. The host gives it memory and
already-inflated bytes; the engine owns the Lua state and the asset parsers.
Nothing in `engine/` reads the dump or touches the Windows API.

## Layout

```
engine/include/r6/r6.h        public API: init, scripts, calls, errors
engine/include/r6/r6_asset.h  XMD / NDWD / NTWD structures and parsers
engine/include/r6/r6_enma.h   Enma DLL byte contract (recovered offsets/enums)
engine/include/r6/r6_course.h road polyline projection and surface flags
engine/include/r6/r6_physics.h  vehicle config, state and simulation API
engine/include/r6/r6_race.h   race rules and EPlayState state machine
engine/include/r6/r6_game.h   game flow and SConfigPlay byte bridge
engine/include/r6/r6_car.h    packed car catalog parser
engine/src/core/              Lua host, engine lifecycle, context bundling
engine/src/assets/            bounds-checked asset parsers + gzip inflate
engine/src/physics/           freestanding vehicle dynamics, course projection, race rules
engine/src/game/              freestanding game-flow state machine and car catalog
engine/src/host/jni.c         Android JNI bridge (not in the host DLL)
engine/compat/                freestanding stdio/stdlib/assert/miniz shims
third_party/lua-5.1.5/        stock Lua 5.1.5 sources (COPYRIGHT included)
third_party/miniz-2.2.0/      miniz 2.2.0 (MIT) for gzip/deflate without a CRT
platform/android/java/        Java side of the JNI bridge
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
- `r6_gzip_expected_size()` / `r6_gzip_inflate()` — RFC 1952 gzip members via
  vendored miniz in raw-deflate mode. `r6_gzip_inflate` reports the required
  capacity on `R6_ERR_BUFFER`; state is one static scratch block, so calls are
  sequential.
- `r6_vehicle_init/reset/step/get_state()`, `r6_vehicle_set_surface()`,
  `r6_vehicle_clamp_to_course()` and `r6_vehicle_config_from_lua()` —
  deterministic car dynamics driven by the loaded spec/tire context, with
  surface grip and road-wall correction. No CRT, no libm and no host calls;
  see `docs/P4_PHYSICS.md`.
- `r6_course_length/project/at()` — arc length and nearest-point projection on
  a host-supplied road polyline.
- `r6_course_descriptor_parse()` — validate and unpack a packed `.r6course`
  blob built from the dump's path, section and stage-model data by
  `tools/engine/course_descriptor.py` and `tools/engine/course_surface.py`.
- `r6_race_init/reset/step/get_state()` and `r6_race_set_rivals()` — countdown,
  lap/goal/timer, wrong-way, off-road and rival contact events using the
  recovered `EPlayState` values; see `docs/P4_COURSE_RACE.md`.
- `r6_game_init/select_car/select_course/start/step/reset()` — car/course
  selection through race result, plus `r6_game_write_config()` /
  `r6_game_read_config()` for the five recovered `SConfigPlay` offsets; see
  `docs/P5_GAME.md`.
- `r6_car_catalog_parse()` and `r6_car_catalog_find_model/find_id()` — parse a
  packed `.r6car` blob built by `tools/engine/car_catalog.py`; see
  `docs/P5_CARS.md`.

## Android bridge

`engine/src/host/jni.c` exposes `com.wmmt.re6rr.Re6Engine` to Java:
`nativeCreate`/`nativeDestroy`, `nativeLoadScript`, `nativeLoadContext`,
`nativeCallVec3`, `nativeCallNumber`, `nativeHasFunction`, `nativeLastError`,
`nativeInflateGzip`, the `nativeVehicle*` family (create from defaults or from
the loaded Lua context, step, read state, destroy) and the `nativeRace*`
family (create with SConfigPlay-like rules, step with course vertices and a
vehicle state, read state, destroy), the `nativeGame*` family (phase flow
and SConfigPlay byte round-trip) and the `nativeCarCatalog*` family (model and
numeric lookup). Java owns assets and
gzip reads and passes plain bytes; the core never touches `AssetManager`. JNI C
is syntax-checked against
`JAVA_HOME/include`, and the Java class is compiled with `javac` by
`build_host.py`. `CMakeLists.txt` links `r6core` into `libr6engine.so` for
`ANDROID`.

## Host build and tests

The host build works without a CRT or Windows SDK: clang emits a DLL with
`-nostdlib /nodefaultlib`, importing only the game's `lua5.1.dll`.

```
python tools/engine/build_host.py --test --dump D:\Games\W6W-05
python tools/engine/test_engine.py --corpus --dump D:\Games\W6W-05
python tools/engine/contexts.py --car CRC_928GT_Masaki --model PLC_928GT --run
python tools/engine/test_physics.py --dump D:\Games\W6W-05
python tools/engine/test_race.py --dump D:\Games\W6W-05
python tools/engine/test_game.py --dump D:\Games\W6W-05
python tools/engine/car_catalog.py --list
python tools/engine/test_catalog.py --dump D:\Games\W6W-05
python tools/engine/course_descriptor.py --list-routes
python tools/engine/course_descriptor.py --route FUKUOKA --out build\tmp\fukuoka.r6course
python tools/engine/course_surface.py --area FUKUOKA --section 101
```

Verified on this dump:

| check | result |
|---|---|
| 4,885 data scripts loaded through the C host | 0 errors |
| `GetTirePos("CRC_928GT_Masaki", 0)` vs Python Lua host | (-7.73, 0.016652, 12.400767), identical |
| `ColorMax()` with `LibraryColor.lua` | 250 |
| `GetHorsepower1st()` with `PLC_928GT_Specification.lua` | 330 |
| `set_number` + scripted getter | 42, round-trips through Lua global |
| ordered context bundle | reproduces the same `GetTirePos` |
| missing function / bad chunk | clean rc + zeroed vector, no crash |
| 1,175 `.tex` files, 5,365 NTWD streams, 17,014 texture headers | C parser matches `tools/assets/ntwd_texture.py` |
| 578 `.mdl` files, 28,516 NDWD groups | C parser matches `tools/assets/ndwd_records.py` |
| 20 gzip containers | output byte-identical to Python `gzip`; bad header rejected, short buffer reports required size |
| JNI C + Java bridge | syntax-checked with `clang`/`javac` against installed JDK |
| vehicle model | idle stable, throttle/brake/steer respond, grass grip cuts yaw 1.839 → 1.017 rad, road clamp holds lateral 1.050 m, 600 mixed frames finite; 928GT config = 242,715 W, 2.508 m wheelbase, 1.546 m track, 5 gears |
| course + race | 100 m straight and 400 m closed square project correctly; lap wrap, countdown, goal, off-road, wrong-way, rival gap/place/contact and 180 coupled vehicle frames pass |
| shipped course descriptor | Fukuoka: 2,816 vertices, 56,344 bytes, closed, sections 101–104, width 2.0–10.0 m; Turnpike: 195 grass + 10 gravel samples; C parser matches the Python generator |
| game flow | select car → course → race → result, invalid transitions rejected, SConfigPlay fields at 0x070/0x450/0x454/0x458/0x45c round-trip, short buffer rejected |
| car catalog | 151 `PLC_*` specs packed to 21,768 bytes, all fields match Python; `PLC_928GT` found by model and id; malformed blobs rejected |

All NTWD streams in this dump are type 2; the type-1 branch is implemented but
has no corpus coverage here. No cube-map or multi-face texture appears either.
The full asset sweep runs with `python tools/engine/test_engine.py --skip-lua
--limit 10000`.

## Android build

`CMakeLists.txt` builds `lua51`, `miniz` and `r6core`, and links them into
`libr6engine.so` for Android. There is no Android NDK/SDK on this machine, so
the CMake/NDK path is authored but not yet compiled. The platform layer still
to be written must:

1. map `sim:data/...` to asset-manager/dump paths and feed gzip bytes through
   `nativeInflateGzip`;
2. build the ordered script lists from `tools/engine/contexts.py` and pass them
   to `nativeLoadContext`;
3. implement the Android UI and Vulkan renderer outside the core.

## Gaps

- Recompiler (P1) still lacks indirect calls/host stubs, bounded loops and
  XMM/SIMD; 16/18 sampled functions pass.
- NTWD parser records blob offsets; BC1/BC3/RGBA8 decompression not ported.
- NDWD parser covers headers and groups; vertex layouts and material chains
  stay in the Python recon tools for now.
- Physics is an original arcade model, not a trace-equivalent of Enma: the
  shipped DLL needs host state to initialise and cannot be driven standalone.
- Course descriptors are synthetic: no road mesh or checkpoint layout has been
  decoded from the dump yet. Race rules are not trace-equivalent of Enma.
- Rival cars, collision response, ghost/phantom and game systems (P5) not
  started.
