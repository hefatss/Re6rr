# Engine core (Phases 3–5)

The engine is a small freestanding C library. The host gives it memory and
already-inflated bytes; the engine owns the Lua state and the asset parsers.
Nothing in `engine/` reads the dump or touches the Windows API.

## Layout

```
engine/include/r6/r6.h        public API: init, scripts, calls, errors
engine/include/r6/r6_asset.h  XMD / NDWD / NTWD structures and parsers
engine/include/r6/r6_audio.h  nuSound2 .nub header, tone and control structures
engine/include/r6/r6_bgm.h  packed BGM id/name/path lookups from wmn6r.exe
engine/include/r6/r6_mixer.h  recovered mixer bus layout, fade and dB conversions
engine/include/r6/r6_engine_sound.h  packed car/tune engine-sound selection and layer envelopes
engine/include/r6/r6_envelope.h  pitch/volume curve evaluation with host math hooks
engine/include/r6/r6_glsl.h   std140 UBO packing and RGBA8 upload descriptors for emitted GLSL
engine/include/r6/r6_glsl_manifest.h  bounds-checked reader for compiled shader bindings
engine/include/r6/r6_gles.h   host sink for validated shader, UBO, texture and draw calls
engine/include/r6/r6_vertex_layout.h  compiled vertex input locations, semantics and masks
engine/include/r6/r6_enma.h   Enma DLL byte contract (recovered offsets/enums)
engine/include/r6/r6_course.h road polyline projection and surface flags
engine/include/r6/r6_physics.h  vehicle config, state and simulation API
engine/include/r6/r6_race.h   race rules and EPlayState state machine
engine/include/r6/r6_game.h   game flow and SConfigPlay byte bridge
engine/include/r6/r6_car.h    packed car catalog parser
engine/include/r6/r6_custom.h packed customization catalog parser
engine/include/r6/r6_story.h  packed story catalog parser
engine/src/core/              Lua host, engine lifecycle, context bundling
engine/src/assets/            bounds-checked asset parsers + gzip inflate
engine/src/audio/             bounds-checked .nub bank, BGM and engine-sound catalogs, mixer bus/fade/dB and envelope curve port; no audio device
engine/src/render/            std140 UBO packing, RGBA8 upload descriptors, binding manifest reader, compiled vertex layout reader and a host-sink GLES call layer; no GL linkage
engine/src/physics/           freestanding vehicle dynamics, course projection, race rules
engine/src/game/              freestanding flow, car/custom/story catalogs
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
- `r6_nub_parse()` / `r6_nub_tone_control()` / `r6_nub_pcm()` — bounds-checked
  nuSound2 bank parse, playback control fields and a zero-copy PCM view over
  host-owned bytes. No mixer, resampling or audio device.
- `r6_mixer_bus_read()/bus_write()/bus_fade()` and
  `r6_mixer_db_to_volume()/volume_to_db()` — access the recovered 68 buses at
  a 0x48 stride and port nuSound2 linear fade and piecewise dB conversions.
  Calibration comes from the caller; no libm or audio device.
- `r6_bgm_parse()` / `r6_bgm_find_id()` / `r6_bgm_find_name()` /
  `r6_bgm_string()` — read packed BGM ids, names and paths recovered from
  `wmn6r.exe`; name matching mirrors `audio_events.bgm_by_name()`, and the
  stop/random ids are flagged. No stream or playback host.
- `r6_esnd_parse()` / `r6_esnd_find()` / `r6_esnd_get_layer()` — read a packed
  car/tune engine-sound mapping and its resolved 16 layer envelopes. The blob
  is built by `tools/engine/engine_sound_catalog.py` from `engmap.tbl` and
  `emtis.tbl`.
- `r6_envelope_eval()` — port of FUN_1407d0dc0's pitch/volume curve. `pow` and
  `exp2` are supplied by host callbacks, so the core stays freestanding while
  the host can use libm for bit-faithful results. Full 16-layer state
  evaluation stays in Python.
- `r6_gles_program_count()/program()` and
  `r6_gles_emit_program()/emit_shader()/emit_uniforms()/emit_texture()/emit_draw()`
  — pair stage records by shader name (223 programs from 446 records), then
  validate GLSL ES version, reflected regions, UBO packing and RGBA8
  descriptors before forwarding calls through a host-provided sink. The core
  has no GL symbols.
- `r6_vertex_init()/get_attrib()/find()/name()` — read a compiled `R6GV`
  vertex-input layout with explicit GLSL locations, DXBC semantics and masks.
  The blob is built by `tools/engine/vertex_layout.py` from the same shader
  export; mesh-to-attribute binding stays with the host.
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
gzip reads and passes plain bytes; the core never touches `AssetManager`.
`Re6Texture` reads NTWD/NTLX headers and RGBA8 pixels, and `Re6Audio` reads
`.nub` headers, tone records, control fields and PCM bytes, `EngineSound` selects car/tune mappings with 16
layer envelopes, `VertexLayout` reads vertex locations, semantics and masks,
and `BgmCatalog` resolves BGM ids and names; none opens an audio or GL device. JNI C
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
python tools/engine/engine_sound_catalog.py --dump D:\Games\W6W-05 --out build\tmp\engine_sound.r6esnd
python tools/engine/bgm_catalog.py --dump D:\Games\W6W-05 --out build\tmp\bgm.r6bgm
python tools/engine/nsxr_shader.py --dump D:\Games\W6W-05 --glsl-dir build\tmp\glsl
python tools/engine/vertex_layout.py --manifest build\tmp\glsl\manifest.json --out build\tmp\glsl\vertex.r6gv
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
| 1,175 `.tex` files, 5,365 NTWD streams, 17,014 texture headers | C parser matches `tools/assets/ntwd_texture.py`; 8 NTLX headers and pixels also match |
| 142 shipped `.nut` textures + one cube face | `r6_nut_decode_rgba()` matches Python RGBA byte-for-byte |
| `Body.nsh` AlphaTest / CustomParameter / PerDraw | `r6_glsl_pack_ubo()` matches Python std140 bytes; short buffer and bad region rejected |
| `Body.nsh` sampler units 0/1/6 | `r6_glsl_texture_upload()` matches Python RGBA8 descriptors for five `.nut` formats; bad format, zero size and overflow rejected |
| `R6GB` compiled bindings | `Body.nsh` round-trips 2 records; pixel stage has 2 cbuffers, 16 regions and 3 sampler pairs; all 446 records parse with 797 cbuffers, 2,029 regions and 526 sampler pairs; short, bad-version and bad-index inputs rejected |
| 578 `.mdl` files, 28,516 NDWD groups | C parser matches `tools/assets/ndwd_records.py` |
| 20 gzip containers | output byte-identical to Python `gzip`; bad header rejected, short buffer reports required size |
| 149 `.nub` banks, 781 tones | C header/tone/control fields and 149 first-tone PCM views match `tools/engine/nub_audio.py`; bad version and short header rejected |
| mixer C port | 68 buses at 0x48 stride, raw offsets 0x00/0x10/0x14/0x18/0x1c, fade over frames and piecewise dB↔volume match `tools/engine/audio_events.py`; bad index, short array and calibration rejected |
| packed BGM table | 142 ids, 8,644 bytes; every name/path/flag and substring lookup matches `tools/engine/audio_events.py`; bad magic, version, truncation and record offsets rejected |
| envelope curve port | all 3,584 layers × 6 rpm points match `engine_sound.envelope_output()` with host `math.pow` callbacks; missing hooks and zero divisor rejected |
| packed engine-sound table | 320 mappings and 3,584 layer envelopes match `tools/engine/engine_sound.py` field-for-field; 195,104 bytes; bad magic, truncation and out-of-range indices rejected |
| GLES host sink | 223 vertex/pixel program pairs from all 446 records; 224-byte reflected UBO, RGBA8 upload and draw forwarded to a mock sink; sink, source, index, region and format errors rejected; sink return codes propagate |
| compiled vertex layout | 823 attributes, 18,143 bytes; locations, semantics and masks match emitted `Body.nsh` GLSL and C lookups; bad magic/version/truncation/index rejected |
| JNI C + Java bridge | syntax-checked with `clang`/`javac` against installed JDK, including car, customization, story catalog, `GlslBindings`, `Re6Texture`, `Re6Audio`, `EngineSound`, `VertexLayout` and `BgmCatalog` wrappers |
| vehicle model | idle stable, throttle/brake/steer respond, grass grip cuts yaw 1.839 → 1.017 rad, road clamp holds lateral 1.050 m, 600 mixed frames finite; 928GT config = 242,715 W, 2.508 m wheelbase, 1.546 m track, 5 gears |
| course + race | 100 m straight and 400 m closed square project correctly; lap wrap, countdown, ordered checkpoints/goal, off-road, wrong-way, rival gap/place/contact, follow-course AI and 180 coupled vehicle frames pass |
| shipped course descriptor | Fukuoka: 2,816 vertices, 56,344 bytes, closed, sections 101–104, width 2.0–10.0 m; Turnpike: 195 grass + 10 gravel samples; C parser matches the Python generator |
| game flow | select car → course → race → result, invalid transitions rejected, 16 named SConfigPlay fields at 0x008–0x63c round-trip, short buffer rejected |
| car catalog | 151 `PLC_*` specs packed to 21,768 bytes, all fields match Python; `PLC_928GT` found by model and id; malformed blobs rejected |
| custom catalog | 250 colours, 107 wheels, 261 aero/parts, 151 tunes and 42 tire scales packed to 70,368 bytes; all five sections round-trip; malformed blobs rejected |
| story catalog | 122 episodes, 3,309 messages, 3,484 events and 647 `drive_story_*` keys packed to 386,681 bytes; sampled records and shared strings round-trip; malformed blobs rejected |

NTWD streams in the sampled `.tex` files are type 2; the type-1 branch is now
covered by the eight NTLX ARGB8 entries in `cmn_dressup_aero_s.nut`, parsed and
decoded through the same C API. No cube-map or multi-face texture appears in
the sampled assets. The full asset sweep runs with
`python tools/engine/test_engine.py --skip-lua --limit 10000`.

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
- BC1/BC2/BC3/ARGB8/A8R8G8B8 decode is in the C core and in
  `tools/engine/nut_texture.py`; GPU texture upload remains outside the core.
- `r6_glsl_pack_ubo()` writes reflected std140 members and
  `r6_glsl_texture_upload()` describes RGBA8 uploads for reflected sampler
  units; shader module creation and GPU calls stay outside the core.
- NDWD parser covers headers and groups; vertex layouts and material chains
  stay in the Python recon tools for now.
- Physics is an original arcade model, not a trace-equivalent of Enma: the
  shipped DLL needs host state to initialise and cannot be driven standalone.
- Course descriptors are synthetic: no road mesh or checkpoint layout has been
  decoded from the dump yet. Race rules are not trace-equivalent of Enma.
- Rival cars, collision response, ghost/phantom and game systems (P5) not
  started.
