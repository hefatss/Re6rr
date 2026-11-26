# Engine core (Phases 3–5)

The engine is a small freestanding C library. The host gives it memory and
already-inflated bytes; the engine owns the Lua state and the asset parsers.
Nothing in `engine/` reads the dump or touches the Windows API.

## Layout

```
engine/include/r6/r6.h        public API: init, scripts, calls, errors
engine/include/r6/r6_asset.h  XMD / NDWD / NTWD structures and parsers
engine/include/r6/r6_audio.h  nuSound2 .nub header, tone, control, string-table, bank-registration view and Sound::Initialize config structures
engine/include/r6/r6_bgm.h  packed BGM lookups, stream fade state and manager id dispatch
engine/include/r6/r6_mixer.h  recovered mixer bus layout, fade and dB conversions
engine/include/r6/r6_engine_sound.h  packed car/tune engine-sound selection and layer envelopes
engine/include/r6/r6_envelope.h  pitch/volume curve evaluation with host math hooks
engine/include/r6/r6_engine_runtime.h  full 16-layer state evaluation and runtime constants
engine/include/r6/r6_voice.h  recovered 0xa0 KeyOn request, 32 chained-voice records and chain arithmetic
engine/include/r6/r6_config_3d.h  config_3d.bin section reader and dB amplitude conversion
engine/include/r6/r6_glsl.h   std140 UBO packing and RGBA8 upload descriptors for emitted GLSL
engine/include/r6/r6_glsl_manifest.h  bounds-checked reader for compiled shader bindings
engine/include/r6/r6_gles.h   host sink for validated shader, UBO, texture and draw calls
engine/include/r6/r6_vertex_layout.h  compiled vertex input locations, semantics and masks
engine/include/r6/r6_enma.h   Enma DLL byte contract (recovered offsets/enums)
engine/include/r6/r6_course.h road polyline projection and surface flags
engine/include/r6/r6_physics.h  vehicle config, state and simulation API
engine/include/r6/r6_race.h   race rules and EPlayState state machine
engine/include/r6/r6_game.h   game flow, SConfigPlay byte bridge and scene camid bridge
engine/include/r6/r6_stage_effect.h  bounds-checked stage-effect sound catalog reader
engine/include/r6/r6_car.h    packed car catalog parser
engine/include/r6/r6_custom.h packed customization catalog parser
engine/include/r6/r6_story.h  packed story catalog parser
engine/src/core/              Lua host, engine lifecycle, context bundling
engine/src/assets/            bounds-checked asset parsers + gzip inflate
engine/src/audio/             bounds-checked .nub bank, BGM and engine-sound catalogs, nuSound2 string tables and Lua bindings, mixer bus/fade/dB, full 16-layer engine evaluation, KeyOn request builder, config_3d.bin reader and bank-registration view; no audio device
engine/src/render/            std140 UBO packing, RGBA8 upload descriptors, binding manifest reader, compiled vertex layout reader and a host-sink GLES call layer; no GL linkage
engine/src/physics/           freestanding vehicle dynamics, course projection, race rules
engine/src/game/              freestanding flow, car/custom/story catalogs and stage-effect sounds
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
- `r6_audio_fade_frames_to_ms()` / `r6_audio_stream_reserve()` — the recovered
  60 fps BGM fade conversion and the 0x20000000 stream-byte cap. Both are
  plain integer functions with no state or device.
- `r6_sound_init_parse()` — validate the shipped 0x28 `Sound::Initialize`
  config (bank/reqid/stream counts), copy its three opaque 64-bit pointer
  slots and report the 0x98 Impl vector byte sizes. No pointer is dereferenced.
- `r6_bank_setup_init()` — read the bank-registration view used by
  nuSound2BankRegister (FUN_18002eb80): version, tone count, data window,
  record table and per-tone length/offset/format count into caller storage.
  On a short tone array, `tone_count` reports the required capacity.
- `r6_bank_slot_find()` — scan the 64 registration slots at a 0x804 stride for
  the first null pointer at `slot*0x804+0x42`; a full table reports not found.
  The slot table stays caller-owned and no bank is registered implicitly.
- `r6_sound_strings_parse()` / `r6_sound_strings_row()` — read the shipped
  `nuSound2BankStr.bin` or `nuSound2ToneStr<BANK>.bin` tables from caller-owned
  bytes. Bank rows yield a name and id; tone rows yield a name and source WAV
  path. The final truncated `ENGINE` bank row has id 0, matching the Python
  parser.
- `r6_audio_binding_count()` / `r6_audio_binding()` /
  `r6_audio_binding_find()` — expose the twelve `luaL_Reg` sound bindings with
  their function addresses, native calls and fixed bank/tone ids. `-1` marks a
  value that is supplied as a Lua argument; no native method is called.
- `r6_mixer_bus_read()/bus_write()/bus_fade()` and
  `r6_mixer_db_to_volume()/volume_to_db()` — access the recovered 68 buses at
  a 0x48 stride and port nuSound2 linear fade and piecewise dB conversions.
  Calibration comes from the caller; no libm or audio device.
- `r6_bgm_parse()` / `r6_bgm_find_id()` / `r6_bgm_find_name()` /
  `r6_bgm_string()` — read packed BGM ids, names and paths recovered from
  `wmn6r.exe`; name matching mirrors `audio_events.bgm_by_name()`, and the
  stop/random ids are flagged. No stream or playback host.
- `r6_bgm_fade_read()` / `r6_bgm_fade_begin()` — read the nine recovered stream
  fade fields and start a fade or the native fallback-stop path using the
  5.333 ms tick conversion and 0x8000000a/0x8000000b/0x80000000 statuses.
  Voice stopping is returned as an id; no audio device is touched.
- `r6_bgm_manager_read()` / `r6_bgm_manager_select()` — read current/next ids
  at `+0x44c`/`+0x450` and apply the six shipped `playBGM` id paths: no change,
  no-sound fade, random rejection, first play, already playing and queued
  change. The returned action tells the host which stream call to make.
- `r6_sound_bin_parse()` — validate `data/sound/config.bin` (magic, version,
  0x50 header, file size, float offset and six section offsets) and copy the
  size, header, float offset and six `(count, offset)` pairs.
- `r6_sound_bank_slot()` / `r6_sound_loop_record()` /
  `r6_sound_positional_record()` — read the sys::Sound::Impl arrays at the
  recovered strides and offsets: 0x20 bank slots, 0x08 SE loop requests and
  0x24 positional SE records. All values are copied; handles stay opaque.
- `r6_esnd_parse()` / `r6_esnd_find()` / `r6_esnd_get_layer()` — read a packed
  car/tune engine-sound mapping and its resolved 16 layer envelopes. The blob
  is built by `tools/engine/engine_sound_catalog.py` from `engmap.tbl` and
  `emtis.tbl`.
- `r6_envelope_eval()` — port of FUN_1407d0dc0's pitch/volume curve. `pow` and
  `exp2` are supplied by host callbacks, so the core stays freestanding while
  the host can use libm for bit-faithful results.
- `r6_engine_runtime_init()/sound()/header()/constant()/state_init()` and
  `r6_engine_eval_layers()` — read EMTIS runtime values from an `R6ERS` blob
  and evaluate all 16 layers from `R6ESND` envelopes. Host callbacks supply
  pow/exp2; no stream, voice or audio device is involved.
- `r6_voice_request_init()/set_ext()/pack()/unpack()` — build or read the
  recovered 0xa0-byte KeyOn record with its two extension blobs and six float
  defaults. `r6_voice_clamp_unit()` and `r6_voice_cents_to_pitch()` port the
  chained-voice appliers; pointer fields are copied as opaque integers and
  never dereferenced. `r6_voice_chain_read()/write()` access the 32 host-owned
  0xd0-byte chained-voice records as 52 f32 slots, and `r6_voice_chain_apply()`
  writes the seven established core-voice fields with native clamp/pitch.
  Speaker matrix, mode and core-voice lookup targets are not written.
- `r6_config_3d_init()` / `r6_config_3d_amplitude()` — parse the shipped
  `config_3d.bin` into caller-owned section storage (10 records plus 6 tail
  words each, angles shifted by 90 degrees) and convert dB to amplitude with
  the host pow hook. Malformed versions, strides, counts and short buffers are
  rejected, as are globals outside the recovered validators (`>0`, `>0`,
  `1..99`, `0..9.9`).
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
- `r6_course_classify_surface()` — classify a shipped `ROAD_NAME` after its
  last `PICE_` prefix as road, grass, gravel or unknown, using the same
  case-insensitive token precedence as `course_surface.classify()`.
- `r6_race_init/reset/step/get_state()` and `r6_race_set_rivals()` — countdown,
  lap/goal/timer, wrong-way, off-road and rival contact events using the
  recovered `EPlayState` values; see `docs/P4_COURSE_RACE.md`.
- `r6_game_init/select_car/select_course/start/step/reset()` — car/course
  selection through race result, plus `r6_game_write_config()` /
  `r6_game_read_config()` for the five recovered `SConfigPlay` offsets; see
  `docs/P5_GAME.md`.
- `r6_scene_write_camid()` / `r6_scene_container_offset()` /
  `r6_scene_runtime_camera()` — copy scene `+0x24` to config `+0x70`, resolve
  the five camera containers at `+0x2d78` with a `0x1b0` stride, and find the
  first non-empty camera record covering a frame. All inputs are caller-owned.
- `r6_car_catalog_parse()` and `r6_car_catalog_find_model/find_id()` — parse a
  packed `.r6car` blob built by `tools/engine/car_catalog.py`; see
  `docs/P5_CARS.md`.
- `r6_stage_effect_parse()` / `r6_stage_effect_get()` /
  `r6_stage_effect_find_symbol()` / `r6_stage_effect_string()` — read the
  `R6STG` blob built by `tools/engine/stage_effect_catalog.py` from the two
  native literal tone ids and three shipped parameter scripts. Symbol lookup
  resolves to bank 3, tones 14/15; strings stay in the caller's blob.

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
`BgmCatalog` resolves BGM ids and names, `BgmManager` applies playBGM id
dispatch, `BgmFade` reads and updates stream fade state, `EngineRuntime`
evaluates 16 layers from both engine blobs, `VoiceRequest` builds and reads
0xa0 KeyOn records with their extension blobs, `Config3D` reads 3D sound
sections, `BankSetup` reads .nub registration views, `AudioStream` exposes
fade timing and stream reservation, `VoiceChain` copies chained-voice records
and applies core fields, `SoundInit` validates the Sound::Initialize config,
`SoundDispatch` copies bank/loop/positional SE records, `SoundConfig` parses
config.bin, `BankSlots` finds free registration slots, `SoundStrings` reads
bank/tone names and WAV paths, `LuaAudioBindings` reads the twelve Lua binding
rows, `CourseSurface` classifies road names, `SceneBridge` copies camid and
resolves camera records,
and `StageEffect` resolves symbolic sounds;
the JNI host supplies
pow/exp2 from libm and sizes tone arrays, but
none opens an audio or GL device. JNI C
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
python tools/engine/engine_runtime_catalog.py --dump D:\Games\W6W-05 --out build\tmp\engine_runtime.r6ers
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
| bank-registration view | all 149 banks and 781 tone length/offset/format rows match `audio_events.bank_setup_view()` and `nub_audio.tones()`; bad version, table, record, short input and capacity rejected |
| bank slot scan | first free slot found across all 64 slots at stride 0x804; full table, short buffer and null arguments rejected |
| nuSound2 string tables | 1 bank table and 8 tone tables (648 rows) match `nub_audio.parse_string_table()`; bank ids 1–7, truncated ENGINE id 0 and SYSTEM tone 47 `select.wav` checked; bad version/size/kind, short and out-of-range inputs rejected |
| Lua sound bindings | all 12 `luaL_Reg` rows match `audio_events.resolved_bindings()`: address, native call and fixed bank/tone; SELECT/CANCEL/CURSOR resolved, bad index and missing name rejected |
| stream arithmetic | BGM frame deltas at 60 fps and stream reservation against the 0x20000000 cap match `audio_events.fade_frames_to_ms()` and `stream_reserve()` |
| Sound::Initialize config | 0x28 config counts, three opaque pointer slots and 0x98 Impl vector sizes match `audio_events.sound_init_facts()` on the shipped exe; bad counts and short input rejected |
| stream fade state | nine fields at the recovered offsets read exact; 2000 ms produces the same frames/step as `audio_events.stream_fade_frames()`/`.stream_fade_step()`, and already-fading, not-playing and fallback-stop paths match the native statuses |
| BGM manager dispatch | current/next at 0x44c/0x450 and all six playBGM id paths (no change, no-sound fade, random rejection, play, already, queue) match `audio_events.BGM_PLAYBACK`; short buffer and null arguments rejected |
| sound dispatch arrays | 8 bank slots, 34 loop records and 2 positional 0x24 records match `audio_events.dispatch_facts()`; out-of-range indices and short buffers rejected |
| config.bin header | shipped 2640-byte file yields the same 0x50 header, float offset 0x70 and six count/offset pairs as `audio_events.config_header()`; bad magic, version, size and section offsets rejected |
| chained-voice records | 32 records x 52 f32 slots read and write byte-exact against the `audio_events.CHAIN_VOICE_STATE` field map; 7 core fields apply with native clamp/pitch and leave other bytes untouched; bad index, short buffer and null arguments rejected |
| mixer C port | 68 buses at 0x48 stride, raw offsets 0x00/0x10/0x14/0x18/0x1c, fade over frames and piecewise dB↔volume match `tools/engine/audio_events.py`; bad index, short array and calibration rejected |
| packed BGM table | 142 ids, 8,644 bytes; every name/path/flag and substring lookup matches `tools/engine/audio_events.py`; bad magic, version, truncation and record offsets rejected |
| envelope curve port | all 3,584 layers × 6 rpm points match `engine_sound.envelope_output()` with host `math.pow` callbacks; missing hooks and zero divisor rejected |
| full engine layer port | 224 sounds × 2 runtime states, 7,168 layer results match `engine_sound.layer_outputs()`; `R6ERS` carries 224 lexical rows, 14 header values and 20 constants in 4,784 bytes; bad sound, capacity and hooks rejected |
| KeyOn request port | three 0xa0-byte request variants, plain and extended, pack byte-for-byte like `audio_events.voice_request()` and unpack every field; unit clamp and cents→pitch match Python; oversize blobs, short buffers and missing pow hook rejected |
| config_3d reader | 5 sections × 10 records and 6 tail words match `audio_events.parse_config_3d()`; dB amplitude matches Python with a host pow callback; bad version, stride, count, truncation, short section capacity and all four global float validators rejected, boundary values accepted |
| packed engine-sound table | 320 mappings and 3,584 layer envelopes match `tools/engine/engine_sound.py` field-for-field; 195,104 bytes; bad magic, truncation and out-of-range indices rejected |
| GLES host sink | 223 vertex/pixel program pairs from all 446 records; 224-byte reflected UBO, RGBA8 upload and draw forwarded to a mock sink; sink, source, index, region and format errors rejected; sink return codes propagate |
| compiled vertex layout | 823 attributes, 18,143 bytes; locations, semantics and masks match emitted `Body.nsh` GLSL and C lookups; bad magic/version/truncation/index rejected |
| JNI C + Java bridge | syntax-checked with `clang`/`javac` against installed JDK, including car, customization, story catalog, `GlslBindings`, `Re6Texture`, `Re6Audio`, `EngineSound`, `VertexLayout`, `BgmCatalog`, `EngineRuntime`, `VoiceRequest`, `Config3D`, `BankSetup`, `AudioStream`, `VoiceChain`, `SoundInit`, `BgmFade`, `BgmManager`, `SoundDispatch`, `SoundConfig`, `BankSlots`, `SoundStrings`, `LuaAudioBindings`, `CourseSurface`, `SceneBridge` and `StageEffect` wrappers |
| vehicle model | idle stable, throttle/brake/steer respond, grass grip cuts yaw 1.839 → 1.017 rad, road clamp holds lateral 1.050 m, 600 mixed frames finite; 928GT config = 242,715 W, 2.508 m wheelbase, 1.546 m track, 5 gears |
| course + race | 100 m straight and 400 m closed square project correctly; lap wrap, countdown, ordered checkpoints/goal, off-road, wrong-way, rival gap/place/contact, follow-course AI and 180 coupled vehicle frames pass |
| shipped course descriptor | Fukuoka: 2,816 vertices, 56,344 bytes, closed, sections 101–104, width 2.0–10.0 m; Turnpike: 195 grass + 10 gravel samples; C parser matches the Python generator |
| game flow | select car → course → race → result, invalid transitions rejected, 16 named SConfigPlay fields at 0x008–0x63c round-trip, short buffer rejected |
| road surface | 558 shipped FUKUOKA LOADLIST labels and 7 precedence cases match `course_surface.classify()`; 405 road, 2 grass, 2 gravel, 156 unknown; null name rejected |
| scene bridge | 5 camid values and all 59 shipped episodes copy to config +0x70 and resolve 0x2d78 + slot*0x1b0; runtime first-match camera equals `scene_bridge.py` and invalid buffers rejected |
| stage-effect catalog | 6 shipped symbolic sounds read from the `R6STG` blob with matching set/symbol/file/tone name/wav, bank 3 tones 14/15, positions and loop flags; symbol lookup, bad magic and short blob checked |
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
