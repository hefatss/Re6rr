# Engine core (Phases 3–5)

The engine is a small freestanding C library. The host gives it memory and
already-inflated bytes; the engine owns the Lua state and the asset parsers.
Nothing in `engine/` reads the dump or touches the Windows API.

## Layout

```
engine/include/r6/r6.h        public API: init, scripts, calls, errors
engine/include/r6/r6_asset.h  XMD / NDWD / NTWD structures and parsers
engine/include/r6/r6_audio.h  nuSound2 .nub header, tone, control, string-table, bank-registration view, layout facts, Sound::Initialize config and Impl tail constants
engine/include/r6/r6_bgm.h  packed BGM lookups, stream fade state and manager id dispatch
engine/include/r6/r6_mixer.h  recovered mixer bus layout, fade and dB conversions
engine/include/r6/r6_engine_sound.h  packed car/tune engine-sound selection and layer envelopes
engine/include/r6/r6_envelope.h  pitch/volume curve evaluation with host math hooks
engine/include/r6/r6_engine_runtime.h  full 16-layer state evaluation and runtime constants
engine/include/r6/r6_engmap.h    WM4_ENGMAP engine sound/group pair reader
engine/include/r6/r6_emtis.h    EMTIS numeric section and source WAV name reader
engine/include/r6/r6_voice.h  recovered 0xa0 KeyOn request, 32 chained-voice records, chain arithmetic, dispatch status and core-voice lookup facts
engine/include/r6/r6_config_3d.h  config_3d.bin section reader and dB amplitude conversion
engine/include/r6/r6_glsl.h   std140 UBO packing and RGBA8 upload descriptors for emitted GLSL
engine/include/r6/r6_glsl_manifest.h  bounds-checked reader for compiled shader bindings
engine/include/r6/r6_nsh.h       bounds-checked NSXR container, DXBC chunk table, STAT/RDEF/signature totals and SHDR operand totals reader
engine/include/r6/r6_shader_cf.h  structured SM4 control-flow map reader
engine/include/r6/r6_shader_usage.h  SHDR cbuffer and texture/sampler usage reader
engine/include/r6/r6_gles.h   host sink for validated shader, UBO, texture and draw calls
engine/include/r6/r6_vertex_layout.h  compiled vertex input locations, semantics and masks
engine/include/r6/r6_enma.h   Enma DLL byte contract (recovered offsets/enums)
engine/include/r6/r6_enma_enums.h  16 recovered Enma enum domains and 1214 names
engine/include/r6/r6_enma_defaults.h  32 recovered Enma SetDefault structs and 89 fields
engine/include/r6/r6_enma_exports.h  172 exported symbol names from the Enma DLL
engine/include/r6/r6_course.h road polyline projection and surface flags
engine/include/r6/r6_physics.h  vehicle config, state and simulation API
engine/include/r6/r6_race.h   race rules and EPlayState state machine
engine/include/r6/r6_game.h   game flow, SConfigPlay byte bridge, scene camid/name bridge and named EES camera/car records
engine/include/r6/r6_context.h  ordered per-car Lua script path templates
engine/include/r6/r6_lua_globals.h  shipped Lua global call-site inventory reader
engine/include/r6/r6_lua_xrefs.h  Lua name to native function/table reference reader
engine/include/r6/r6_lua_inventory.h  shipped Lua count, directory and name reader
engine/include/r6/r6_asset_inventory.h  shipped extension, magic, folder and shader sample counts
engine/include/r6/r6_pe_inventory.h  shipped PE header, .pdata, import and symbol inventory reader
engine/include/r6/r6_name_runs.h  shipped string-pointer run, name and code-reference reader
engine/include/r6/r6_lua_reg_tables.h  shipped luaL_Reg table and function RVA reader
engine/include/r6/r6_path_strings.h  shipped executable and source path string reader
engine/include/r6/r6_enma_sim.h  shipped CGameInput getter probes and default config image reader
engine/include/r6/r6_ref_words.h  shipped reference-word xref reader
engine/include/r6/r6_pdata_stats.h  shipped .pdata size buckets and largest functions reader
engine/include/r6/r6_string_xrefs.h  shipped raw string-to-RVA xref reader
engine/include/r6/r6_honor_schema.h  recovered unlock/honor condition schema reader
engine/include/r6/r6_scene_env.h  shipped Environment.Lua value inventory reader
engine/include/r6/r6_stage_effect.h  bounds-checked stage-effect sound catalog reader
engine/include/r6/r6_car.h    packed car catalog parser
engine/include/r6/r6_custom.h packed customization catalog parser
engine/include/r6/r6_story.h  packed story catalog parser
engine/src/core/              Lua host, engine lifecycle, context bundling
engine/src/assets/            bounds-checked asset parsers + gzip inflate
engine/src/audio/             bounds-checked .nub bank, BGM and engine-sound catalogs, WM4_ENGMAP and EMTIS text tables, nuSound2 string tables and Lua bindings, mixer bus/fade/dB, full 16-layer engine evaluation, KeyOn request builder, config_3d.bin reader and bank-registration view; no audio device
engine/src/render/            std140 UBO packing, RGBA8 upload descriptors, binding manifest reader, NSXR/DXBC container reader, compiled vertex layout reader and a host-sink GLES call layer; no GL linkage
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
- `r6_ndwd_parse_subrecord()` / `r6_ndwd_parse_chain_record()` /
  `r6_ndwd_string()` — read raw NDWD subrecord tokens, the bounded chain record
  at `sub+0x20+extra*0x18`, and NUL-terminated strings at
  `0x30+sum(section_size)+offset`. All 44,176 shipped subrecords have `extra=0`
  and a flag-zero raw record, which the native loader rejects; no material or
  texture meaning is inferred.
- `r6_nut_container_facts()` — copy the 11 file-level NTWD/NTLX header values:
  verbatim container tag, version, entries, total, payload/descriptor sizes,
  packed words, first GIDX, derived payload offset and the empirical
  exact-layout flag. No descriptor or pixel bytes are dereferenced.
- `r6_nut_layout_facts()` — derive the 16-byte-aligned mip layout of one
  NTWD/NTLX descriptor: full declared payload including cube faces, per-face
  size, aligned level-0 bytes, declared/available levels and the cube flag.
  The three shipped short-mip entries report fewer available levels; no file
  or pixel data is read.
- `r6_nub_parse()` / `r6_nub_tone_control()` / `r6_nub_tone_getters()` /
  `r6_nub_setup_bytes()` / `r6_nub_pcm()` — bounds-checked nuSound2 bank parse,
  playback control fields, the four user parameters at record `+0xac..+0xb8`
  plus codec-1 `PCM length / block align` total samples, the opaque 0x30 bytes
  at record `+0x30..+0x5f` copied verbatim at bank registration, and a
  zero-copy PCM view over host-owned bytes. No envelope meaning, mixer,
  resampling or audio device.
- `r6_audio_fade_frames_to_ms()` / `r6_audio_stream_reserve()` — the recovered
  60 fps BGM fade conversion and the 0x20000000 stream-byte cap. Both are
  plain integer functions with no state or device.
- `r6_sound_init_parse()` — validate the shipped 0x28 `Sound::Initialize`
  config (bank/reqid/stream counts), copy its three opaque 64-bit pointer
  slots and report the 0x98 Impl vector byte sizes. No pointer is dereferenced.
- `r6_sound_impl_tail()` — return the verbatim shipped Impl tail constants:
  four zero qwords at `+0x60`, floats `1.0` at `+0x80`/`+0x88` and
  `0xFFFFFFFF` at `+0x90`. No Impl object is allocated or written.
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
  parser. `r6_sound_strings_find()` resolves the first exact row name in
  either table; `r6_sound_strings_find_value()` resolves the first tone row with
  an exact WAV path. Both leave the other row fields available through
  `r6_sound_strings_row()`.
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
- `r6_engmap_parse()` — read the `WM4_ENGMAP` text table into 320 engine
  sound/group pairs, rejecting count mismatches and conflicting groups.
- `r6_emtis_parse()` / `r6_emtis_name()` / `r6_emtis_find_name()` — read the
  `EMTIS` header, 16365 numeric tokens, seven marker-delimited sections with
  their first eight tokens, the four source-name prefix counts and 416 copied
  source WAV names. `find_name()` returns the first exact name line. No meaning
  is assigned to the numeric sections.
- `r6_audio_layout_facts()` — copy the 64 bank slot offsets, cleanup record
  layout, stream reserve/limit, bank version and voice/meta table constants.
  No pointer is dereferenced.
- `r6_voice_dispatch_facts()` — copy the recovered bank/3D null error codes,
  chained-tone error and modes, extension blob layout, game vector sources and
  call-site addresses. No native method is called or pointer dereferenced.
- `r6_voice_keyon_users()` — copy the 14 wrapper addresses and three group
  shapes for plain, point and line KeyOn users: 6/6/2 addresses, extended
  flags, position float counts and the point group's 0x0c secondary vector.
  Absent arguments are zero; no wrapper is called.
- `r6_voice_core_table_facts()` — copy the 192-entry core-voice table offset,
  stride, chain mode and lookup address from `FUN_18001ed00`; instance storage
  stays host owned.
- `r6_config_3d_init()` / `r6_config_3d_amplitude()` — parse the shipped
  `config_3d.bin` into caller-owned section storage (10 records plus 6 tail
  words each, angles shifted by 90 degrees) and convert dB to amplitude with
  the host pow hook. Malformed versions, strides, counts and short buffers are
  rejected, as are globals outside the recovered validators (`>0`, `>0`,
  `1..99`, `0..9.9`).
- `r6_nsh_parse()` — validate an `NSXR` header, its two `0x10`-byte records and
  each `DXBC` digest/version/size, then return the five chunk tags, offsets and
  sizes per record. SHDR/RDEF/ISGN/OSGN payload decoding stays in the export
  tools; no D3D or file access is involved. `r6_nsh_chunk_find()` resolves a
  four-CC tag to the first matching chunk in one parsed record.
  `r6_dxbc_stat_facts()` copies the summed 29-field `STAT` vector from the 446
  shipped records, including 20,563 instructions, 2,888 declarations and 680
  texture samples; `unknown_*` fields stay verbatim and no chunk is read.
  `r6_dxbc_reflection_facts()` / `r6_dxbc_reflection_creator()` copy the 23
  summed RDEF fields across the same 446 records (797 cbuffers, 2,029
  variables, 1,849 resources, 64,976 cbuffer bytes) and the one shipped creator
  string; detailed RDEF names and per-record layout stay in Python.
  `r6_shdr_operand_facts()` copies the seven summed SM4 operand and modifier
  totals from the same 446 SHDR chunks: 43,827 instruction operands, 4,737
  declaration operands, 974 `neg`, 55 `abs`, 5,693 immediates, 1,935
  `TestNonZero` and 408 `Saturate` instructions. No bytecode is translated.
  `r6_dxbc_signature_facts()` copies the seven summed ISGN/OSGN chunk and entry
  counts: 892 chunks, 1,813 raw inputs, 1,590 non-`SV_` inputs, 1,457 outputs
  and 223 skipped `SV_POSITION` vertex inputs.
- `r6_shader_cf_parse()/record()/name()/find()/block()/case()/index()` — read
  the derived `R6SCF` map of 303 `IF`/`LOOP`/`SWITCH` blocks across the 446
  SHDR records, with 2,448 case starts and 2,478 break/continue instruction
  indices. Blocks carry source/end indices, `ELSE`, case spans and innermost
  break/continue spans; no branch target is invented.
- `r6_shader_usage_parse()/record()/name()/find()/uniform()/find_uniform()/resource()/find_resource()/declared()` —
  read the derived `R6SCU` per-record maps of 1,645 resolved uniform keys,
  1,052 resource/sampler keys and 1,052 declaration names across 446 records.
  Counts cover 5,502 static cbuffer operands, 8 dynamic indices, 1,360
  resource/sampler uses, zero unmapped bindings and zero dynamic bindings.
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
- `r6_scene_identity_parse()/record()/name()/find()` — read the derived `R6SCI`
  byte-equality map for `CamData.EES` versus `CamData<camid>.EES` across the 59
  shipped `Environment.Lua` episodes: 58 match, `ESeries_055` (camid 2) does
  not. Equality is copied as a fact; no camera field is reinterpreted.
- `r6_ees_camera_fields()` — copy the 31 fields named by `FUN_1401e0330` from
  one `0x160`-byte `.EES` camera record. Native names and declared types are
  preserved, including the f32 members printed with `%d`.
- `r6_ees_parse()` — validate an `EventScene2` header and return the typed
  arrays (offset/count/stride/size) for camera or car containers. Both shipped
  header sizes and all five array kinds are preserved.
- `r6_ees_camera_at_frame()` — return the last non-empty `0x160` camera record
  covering a frame, matching `FUN_1401c8f60`; `exact=1` compares start only and
  otherwise the end is `trunc(start + duration)`. This is distinct from the
  first-match runtime record lookup in `r6_scene_runtime_camera()`.
- `r6_ees_car_effect_copy()` — copy the 40 fields of a `0xa0` EES `car_effect`
  record into the `0xe0` runtime layout recovered from `FUN_1401cc390`.
- `r6_ees_camera_accept_type()` — the `FUN_1401ca060` type 0/2 filter.
- `r6_ees_car_disp()` — read one `0x180` display record: car id, flag byte,
  16-f32 matrix and yaw; non-finite yaw gives zero yaw units.
- `r6_ees_car_info()` — read the int32 id of a `0x8c` car_info record.
- `r6_glsl_coverage_facts()` — return the aggregate GLES lowering facts for all
  446 shipped SHDR records: 20,563 instructions split into 11,184 direct,
  2,720 lowered, 5,979 control and 680 texture opcodes across 43 classified
  opcodes with zero unknown. It is a lowering plan, not an emitter.
- `r6_glsl_bindings_find_record()` — first exact shader-name record in the
  compiled `R6GB` manifest; names and offsets are copied, never dereferenced as
  native pointers.
- `r6_lua_globals_parse()` / `r6_lua_globals_row()` / `r6_lua_globals_find()` — read the derived `R6LUA`
  inventory of 219 globals looked up by the executable, with call counts and
  seven category indices. Lua bodies remain in shipped data scripts; no binding
  is invented.
- `r6_lua_xref_parse()/row()/name()/find()/func()/table()/user()/find_rva()` —
  read the derived `R6XRF` map of those 219 names to 222 function RVAs, 28
  string/pointer-table RVAs and their 65 loading functions. `find_rva()` returns
  every (row, kind, which, item) location with an exact RVA. RVAs are reported,
  never executed.
- `r6_lua_inventory_parse()/name()/dir()/find()/symbol()/find_symbol()` — read
  the derived `R6LSI` counts for 4,885 + 167 Lua files across 158 directories,
  the 1,252 defined names and the 215 native / 280 undefined top name/count
  pairs. `find_symbol()` returns the first exact name in one root/kind table.
- `r6_asset_inventory_parse()/ext()/magic()/folder()/find_ext()/find_magic()/find_folder()/shader()/find_shader()` — read the
  derived `R6AIV` counts: 32 extension rows, 7 inner-magic rows, 27 top-folder
  rows and 40 shader samples with copied paths and 16-byte prefixes.
- `r6_pe_inventory_parse()/func()/func_find()/func_cover()/dll()/dll_find()/import()/import_find()/section()/export()/tls()/directory()/directory_find()/pdb()/sha256()/exe_path()`
  — read the derived `R6PEI` counts: 70,377 `.pdata` rows, 28 DLLs, 825
  imports, 7 sections, 8 directories, 2 exports and one TLS callback.
  `func_cover()` resolves any interior RVA to its sorted non-overlapping
  `[begin, end)` row; gaps return `R6_ERR_NOT_FOUND`. The header also carries
  `.pdata` RVA range/entry size, symbol table/count, debug type and copied
  SHA-256 / source path offsets. RVAs are copied as numbers; no PE bytes are
  mapped or executed.
- `r6_name_runs_parse()/run()/name()/run_name()/user()/find()/find_user()` — read the
  derived `R6NTR` inventory of 521 string-pointer runs, 13,283 names and 888
  code references. `find()` returns the first exact name by run, local and
  global index; `find_user()` returns the first code-reference row with an
  exact RVA. RVAs are never dereferenced; the Java bridge rejects negative or
  wider-than-U32 RVA inputs before the cast.
- `r6_lua_reg_parse()/table()/entry()/table_entry()/user()/find()` — read the
  derived `R6LREG` inventory of 3 shipped `luaL_Reg` tables and 42 name/function
  rows. Signature-like labels are copied verbatim, not interpreted.
- `r6_path_strings_parse()/group()/get()/group_get()/find()` — read the derived
  `R6PST` inventory of 1,271 executable strings and 422 source paths.
- `r6_enma_sim_parse()/getter()/hit()/config()/find()` — read the derived `R6ESIM`
  facts: six `CGameInput` getters, four single-offset probe hits and the
  4096-byte default config image. Values are copied as raw bits.
- `r6_ref_words_parse()/word()/xref()/word_xref()/find()/find_rva()` — read the
  derived `R6REF` inventory of 98,805 raw reference words and 174,507 instruction
  RVAs. `find_rva()` returns every global xref index with that exact RVA.
- `r6_pdata_stats_parse()/bucket()/largest()/find()` — read the derived `R6PDS`
  statistics: seven function-size buckets and the twenty largest `.pdata`
  functions with copied unwind chain fields.
- `r6_string_xref_parse()/name()/rva()/name_rva()/find()/find_rva()` — read the
  derived `R6SXR` scan totals and 195 raw string-xref names with 222 instruction
  RVAs. `find_rva()` returns every global RVA index with that exact RVA, so
  many-to-one hits are not collapsed to the first one.
- `r6_context_path()` — produce one of the 12 slash-separated relative Lua
  script paths in shipped load order (tire, position, shader, specification,
  colour) from a car and model name. Existence checks and script bytes stay
  with the host.
- `r6_environment_parse()` — read one shipped `Environment.Lua` text file into
  the eight scene slots; unrecognized keys and malformed decimal values become
  zero, matching the Python regex reader.
- `r6_scene_pack()` — write the eight environment slots into a `0x28` scene
  buffer. `r6_scene_names_parse()` / `r6_scene_names_get()` read the `R6SCN`
  blob built by `tools/engine/scene_config_catalog.py` and apply the shipped
  car/stage/day indexing: `-1` and out-of-range cars give `PLC_NON`, stage uses
  `value-1`, day uses the raw value. `r6_scene_names_find()` resolves an exact
  name back to that id; stage ids returned are one-based.
  `r6_live_stage_facts()` copies the three verbatim live-config `eStage` copies
  in the `CSeq::Init` builder (`0x258→0x1b0`, `0x3d0→0x308`, `0x630→0x450`)
  and four native addresses. No copy is performed and scene-to-config
  propagation remains unproven.
- `r6_native_names_parse()` / `r6_native_names_get()` read the `R6NAM` blob
  built by `tools/engine/native_names_catalog.py` from nine shipped pointer-name
  runs (sequence, tk_ari, stage_time, tips_end, flash, parts, honor,
  check_honor and vinyl_blend). `r6_native_names_find()` resolves an exact name
  to its row index in one table. No name tables are fabricated.
- `r6_car_catalog_parse()` and `r6_car_catalog_find_model/find_id()` — parse a
  packed `.r6car` blob built by `tools/engine/car_catalog.py`; see
  `docs/P5_CARS.md`. `r6_car_catalog_engine_sound()` reads the verbatim
  `EngineSound` field added in version 3; older blobs return
  `R6_ERR_FORMAT`. `r6_car_catalog_text_field()` copies the six cp932 display
  fields; v4 adds Japanese name, `CarNameForPG`, glade and year.
- `r6_story_catalog_summary()` — count stored message/event phases, event kinds,
  branch/ending/environment flags, enum-zero episodes and empty key values in a
  validated `.r6story` catalog. No unlock or mission-order semantics are
  inferred; see `docs/P5_STORY.md`.
- `r6_story_keys_parse()/name()/find()/fact()` — read the `.r6sk` inventory of
  101 story keys hard-coded by `wmn6r.exe`, with exact ASCII lookup and the
  direct/table source fact; see `docs/P5_STORY.md`.
- `r6_enma_enum_parse()/name()/find_domain()/count()/value()/find()` — read the derived
  `R6EME` inventory of 16 Enma enums and 1214 value names recovered from the
  shipped DLL exports, with ordinal and value lookups.
- `r6_enma_defaults_parse()/struct()/find()/field()/find_field()` — read the derived `R6EDF` layout
  of 32 `SetDefault` structs, 89 constant writes and 2642 bytes recovered from
  the shipped DLL. Byte arrays are copied; no struct or DLL is instantiated.
- `r6_enma_exports_parse()/name()/find()` — read the derived `R6EEX` export-name
  inventory from `Wg6Enma_Release_IDL0.dll`; lookup is by exact mangled name.
- `r6_scene_env_parse()/name()/row()/find()` — read the derived `R6SES` inventory
  of 122 `ESeries_*` directories, 59 with `Environment.Lua`, including stage,
  camera and four actor slots per directory and aggregate value domains.
- `r6_honor_schema_parse()` / `r6_honor_schema_type()` /
  `r6_honor_schema_find_type()` / `r6_honor_schema_field()` /
  `r6_honor_schema_find_field()` — read the derived `R6HON` schema with 13 condition
  types and 60 ordered field labels. `r6_honor_type1_facts()` additionally
  copies the type-1 ABI: 0xc0-byte object, four stored field offsets, 1..20
  `clear_bits` domain, ten Property slots and the deserializer/constructor/
  tune-helper addresses. No per-episode predicate instances are present in the
  shipped dump, so none are inferred.
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
and SConfigPlay byte round-trip), the `nativeCarCatalog*` family (model,
numeric, EngineSound, cp932 text and exact model/ID lookup), the
`nativeStoryKeys*` family and the `nativeCustomCatalog*`
family (records plus exact colour/wheel/aero/tune lookups). Java owns assets and
gzip reads and passes plain bytes; the core never touches `AssetManager`.
`Re6Texture` reads NTWD/NTLX headers and RGBA8 pixels, `Re6Container` walks
inflated XMD.001 stream tables and copies stream bytes/tags,
`Re6MeshRecords` reads raw NDWD groups/subrecords/chain records and strings,
and `Re6Audio` reads
`.nub` headers, tone records, control fields, opaque registration bytes and PCM
bytes, `EngineSound` selects car/tune mappings with 16
layer envelopes, `VertexLayout` reads vertex locations, semantics and masks,
`BgmCatalog` resolves BGM ids and names, `BgmManager` applies playBGM id
dispatch, `BgmFade` reads and updates stream fade state, `EngineRuntime`
evaluates 16 layers from both engine blobs, `VoiceRequest` builds and reads
0xa0 KeyOn records with their extension blobs, `Config3D` reads 3D sound
sections, `BankSetup` reads .nub registration views, `AudioStream` exposes
fade timing and stream reservation, `VoiceChain` copies chained-voice records
and applies core fields, `SoundInit` validates the Sound::Initialize config,
`SoundDispatch` copies bank/loop/positional SE records, `SoundConfig` parses
config.bin, `BankSlots` finds free registration slots, `SoundStrings` finds
bank/tone names and WAV paths, `LuaAudioBindings` reads the twelve Lua binding
rows, `CourseSurface` classifies road names, `SceneBridge` copies camid and
resolves camera records, `EesContainer` parses the shipped headers, `EesCamera` reads the 31 named camera
fields, filters type 0/2 and resolves frames with last-match semantics,
`EesCarInfo` reads car ids, `EesCarEffect` copies the 40
runtime fields, `EesCarDisp` reads display records, `AudioLayoutFacts` exposes bank/voice table offsets, `VoiceDispatchFacts`
exposes recovered status codes and call sites, `VoiceCoreTableFacts` exposes the
192-entry lookup layout, `ContextPaths` returns ordered Lua bundle paths, `LuaGlobals` exposes the 219-call-site inventory, `LuaXrefs` maps names to native refs and resolves an RVA to every location using it, `LuaInventory` counts 158 Lua directories, `AssetInventory` reads 32 extensions and 27 folders, `PeInventory` reads 70,377 `.pdata` rows, 825 imports and 8 PE directories, `NameRuns` reads 521 pointer runs with 13,283 names, `LuaRegTables` reads 3 `luaL_Reg` tables with 42 rows, `PathStrings` reads 1,693 exe/source path strings, `EnmaSimFacts` reads 6 input getters and 4096 config bytes, `RefWords` reads 98,805 words, 174,507 xrefs and all reverse RVA hits, `PdataStats` reads 7 size buckets and 20 largest functions, `StringXrefs` reads 195 raw string xrefs, scan totals and all reverse RVA hits, `EnmaEnums` exposes 16 enum domains, `EnmaDefaults` copies 32 SetDefault layouts, `EnmaExports` resolves 172 DLL symbols, `SceneEnvStats` inventories 122 scene directories, `HonorSchema` reads the 13 predicate types, `EnvironmentLua` parses scene scripts, `NativeNames`
resolves shipped pointer-table names, `SceneConfig` packs scenes and resolves
native names, and
`StageEffect`
resolves symbolic sounds. Java `long` key lookups in `EnmaEnums.find`,
`EnmaDefaults.findField`, `NameRuns.findUser`, `RefWords.find`,
`PdataStats.find` and `PeInventory.funcFind` reject negative or
wider-than-U32 inputs before the native cast;
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
| 1,250 `.tex` files, 5,664 NTWD streams, 17,877 texture headers | C parser matches `tools/assets/ntwd_texture.py`; 143 NTLX entries and pixels also match |
| 11,151 `.nut` files | `r6_nut_container_facts()` matches `nut_texture.py` on all 11 header fields; 11,008 NTWD / 143 NTLX and 9,599 exact-layout rows; bad magic, short blob, version 3, zero entries, small descriptor and null input/output rejected |
| 142 shipped `.nut` textures + one cube face | `r6_nut_decode_rgba()` matches Python RGBA byte-for-byte |
| 50,180 shipped NTWD type-2 entries | `r6_nut_layout_facts()` matches `nut_texture.expected_size()`, `level_size()` and `available_levels()`; 228 cube entries and three short-mip rows included; bad format/levels/width and null inputs rejected |
| `Body.nsh` AlphaTest / CustomParameter / PerDraw | `r6_glsl_pack_ubo()` matches Python std140 bytes; short buffer and bad region rejected |
| `Body.nsh` sampler units 0/1/6 | `r6_glsl_texture_upload()` matches Python RGBA8 descriptors for five `.nut` formats; bad format, zero size and overflow rejected |
| `R6GB` compiled bindings | `Body.nsh` round-trips 2 records; pixel stage has 2 cbuffers, 16 regions and 3 sampler pairs; all 446 records parse with 797 cbuffers, 2,029 regions and 526 sampler pairs; name find, short, bad-version and bad-index inputs rejected |
| GLES lowering facts | C totals match `nsxr_shader.glsl_coverage()` on all 446 records: 20,563 instructions, 11,184 direct / 2,720 lowered / 5,979 control / 680 texture, 43 opcodes and zero unknown; null output ignored |
| 578 `.mdl` files, 28,516 NDWD groups | C parser matches `tools/assets/ndwd_records.py` |
| 610 `.mdl` + 371 `.nud` files, 23,570 NDWD streams | header, group, 44,176 subrecords, 44,176 raw chain records and 30,885 group strings match `ndwd_records.py`; flag-gated synthetic chain and bad offsets/capacities rejected |
| 20 gzip containers | output byte-identical to Python `gzip`; bad header rejected, short buffer reports required size |
| 149 `.nub` banks, 781 tones | C header/tone/control fields and 149 first-tone PCM views match `tools/engine/nub_audio.py`; all 781 codec-1 getter rows expose exact user params and total samples, and all 781 opaque 0x30 registration byte blocks match the raw records; bad version, short header, bad codec, bad record and null output/blob rejected |
| bank-registration view | all 149 banks and 781 tone length/offset/format rows match `audio_events.bank_setup_view()` and `nub_audio.tones()`; bad version, table, record, short input and capacity rejected |
| bank slot scan | first free slot found across all 64 slots at stride 0x804; full table, short buffer and null arguments rejected |
| nuSound2 string tables | 1 bank table and 8 tone tables (648 rows) match `nub_audio.parse_string_table()`; bank ids 1–7, truncated ENGINE id 0 and SYSTEM tone 47 `select.wav` checked; all 648 row names and 601 distinct WAV paths resolve through `find`/`findValue`, absent name/path rejected, bad version/size/kind, short and out-of-range inputs rejected |
| Lua sound bindings | all 12 `luaL_Reg` rows match `audio_events.resolved_bindings()`: address, native call and fixed bank/tone; SELECT/CANCEL/CURSOR resolved, bad index and missing name rejected |
| stream arithmetic | BGM frame deltas at 60 fps and stream reservation against the 0x20000000 cap match `audio_events.fade_frames_to_ms()` and `stream_reserve()` |
| Sound::Initialize config | 0x28 config counts, three opaque pointer slots, 0x98 Impl vector sizes and tail constants match `audio_events.sound_init_facts()` on the shipped exe; bad counts, short input and null output rejected |
| stream fade state | nine fields at the recovered offsets read exact; 2000 ms produces the same frames/step as `audio_events.stream_fade_frames()`/`.stream_fade_step()`, and already-fading, not-playing and fallback-stop paths match the native statuses |
| BGM manager dispatch | current/next at 0x44c/0x450 and all six playBGM id paths (no change, no-sound fade, random rejection, play, already, queue) match `audio_events.BGM_PLAYBACK`; short buffer and null arguments rejected |
| sound dispatch arrays | 8 bank slots, 34 loop records and 2 positional 0x24 records match `audio_events.dispatch_facts()`; out-of-range indices and short buffers rejected |
| config.bin header | shipped 2640-byte file yields the same 0x50 header, float offset 0x70 and six count/offset pairs as `audio_events.config_header()`; bad magic, version, size and section offsets rejected |
| chained-voice records | 32 records x 52 f32 slots read and write byte-exact against the `audio_events.CHAIN_VOICE_STATE` field map; 7 core fields apply with native clamp/pitch and leave other bytes untouched; bad index, short buffer and null arguments rejected |
| audio layout facts | 5 slot fields, 3 cleanup record fields, stream reserve/limit, version and 4 voice/meta fields match `audio_events.py`; null output is a no-op |
| core-voice lookup facts | 192 entries at +0x44 stride 0x178, mode 7 and lookup address match `audio_events.py`; null output is a no-op |
| EMTIS | all 16365 tokens, 7 sections, 44 header values and all 416 names match `audio_tables.parse_emtis()`; name/find, bad magic, short capacity and null inputs rejected |
| WM4_ENGMAP | all 320 shipped sound/group pairs match `audio_tables.parse_engmap()`; conflicts, bad magic and null inputs rejected |
| voice dispatch facts | 8 bank errors, 3 null errors, chain error/modes, ext blob layout, game vector sources, 8 addresses and 14 KeyOn wrapper addresses match `audio_events.py`; null output is a no-op |
| mixer C port | 68 buses at 0x48 stride, raw offsets 0x00/0x10/0x14/0x18/0x1c, fade over frames and piecewise dB↔volume match `tools/engine/audio_events.py`; bad index, short array and calibration rejected |
| packed BGM table | 142 ids, 8,644 bytes; every name/path/flag and substring lookup matches `tools/engine/audio_events.py`; bad magic, version, truncation and record offsets rejected |
| envelope curve port | all 3,584 layers × 6 rpm points match `engine_sound.envelope_output()` with host `math.pow` callbacks; missing hooks and zero divisor rejected |
| full engine layer port | 224 sounds × 2 runtime states, 7,168 layer results match `engine_sound.layer_outputs()`; `R6ERS` carries 224 lexical rows, 14 header values and 20 constants in 4,784 bytes; bad sound, capacity and hooks rejected |
| KeyOn request port | three 0xa0-byte request variants, plain and extended, pack byte-for-byte like `audio_events.voice_request()` and unpack every field; unit clamp and cents→pitch match Python; oversize blobs, short buffers and missing pow hook rejected |
| config_3d reader | 5 sections × 10 records and 6 tail words match `audio_events.parse_config_3d()`; dB amplitude matches Python with a host pow callback; bad version, stride, count, truncation, short section capacity and all four global float validators rejected, boundary values accepted |
| packed engine-sound table | 320 mappings and 3,584 layer envelopes match `tools/engine/engine_sound.py` field-for-field; 195,104 bytes; bad magic, truncation and out-of-range indices rejected |
| GLES host sink | 223 vertex/pixel program pairs from all 446 records; 224-byte reflected UBO, RGBA8 upload and draw forwarded to a mock sink; sink, source, index, region and format errors rejected; sink return codes propagate |
| NSXR container | all 223 shipped `.nsh` files, 446 records and 2230 DXBC chunks match `nsxr_shader.parse_nsh()`; all 29 summed `STAT` fields, 23 summed `RDEF` fields, 7 SHDR operand/modifier totals, 7 ISGN/OSGN totals and one creator string match; chunk find, short input, bad magic and bad sizes rejected |
| SM4 control flow | 446 records, 303 blocks, 2448 cases and 2478 break/continue indices match `nsxr_shader.control_flow()`; `Body.nsh` pixel has two 9-case switches; bad blob, index, stage and capacity rejected |
| SHDR usage map | 446 records, 1645 uniform rows, 1052 resource rows and 1052 declarations match `nsxr_shader`; 5502 static cbuffer operands, 8 dynamic, 1360 resource uses, zero dynamic/unmapped; bad blob, index and stage rejected |
| compiled vertex layout | 823 attributes, 18,143 bytes; locations, semantics and masks match emitted `Body.nsh` GLSL and C lookups; bad magic/version/truncation/index rejected |
| JNI C + Java bridge | syntax-checked with `clang`/`javac` against installed JDK, including car, customization, story catalog, `GlslBindings`, `NshContainer`, `Re6Texture`, `Re6Audio`, `EngineSound`, `VertexLayout`, `BgmCatalog`, `EngineRuntime`, `EngmapTable`, `EmtisTable`, `VoiceRequest`, `Config3D`, `BankSetup`, `AudioStream`, `VoiceChain`, `SoundInit`, `BgmFade`, `BgmManager`, `SoundDispatch`, `SoundConfig`, `BankSlots`, `SoundStrings`, `LuaAudioBindings`, `CourseSurface`, `SceneBridge`, `EesContainer`, `EesCamera`, `EesCarInfo`, `EesCarEffect`, `EesCarDisp`, `AudioLayoutFacts`, `VoiceDispatchFacts`, `VoiceCoreTableFacts`, `ContextPaths`, `LuaGlobals`, `LuaXrefs`, `LuaInventory`, `AssetInventory`, `PeInventory`, `NameRuns`, `LuaRegTables`, `PathStrings`, `EnmaSimFacts`, `RefWords`, `PdataStats`, `StringXrefs`, `EnmaEnums`, `EnmaDefaults`, `EnmaExports`, `SceneEnvStats`, `HonorSchema`, `EnvironmentLua`, `NativeNames`, `SceneConfig`, `ShaderControlFlow`, `ShaderUsage` and `StageEffect` wrappers |
| vehicle model | idle stable, throttle/brake/steer respond, grass grip cuts yaw 1.839 → 1.017 rad, road clamp holds lateral 1.050 m, 600 mixed frames finite; 928GT config = 242,715 W, 2.508 m wheelbase, 1.546 m track, 5 gears |
| course + race | 100 m straight and 400 m closed square project correctly; lap wrap, countdown, ordered checkpoints/goal, off-road, wrong-way, rival gap/place/contact, follow-course AI and 180 coupled vehicle frames pass |
| shipped course descriptor | Fukuoka: 2,816 vertices, 56,344 bytes, closed, sections 101–104, width 2.0–10.0 m; Turnpike: 195 grass + 10 gravel samples; C parser matches the Python generator |
| game flow | select car → course → race → result, invalid transitions rejected, 16 named SConfigPlay fields at 0x008–0x63c round-trip, short buffer rejected |
| road surface | 558 shipped FUKUOKA LOADLIST labels and 7 precedence cases match `course_surface.classify()`; 405 road, 2 grass, 2 gravel, 156 unknown; null name rejected |
| scene bridge | 5 camid values and all 59 shipped episodes copy to config +0x70 and resolve 0x2d78 + slot*0x1b0; runtime first-match camera equals `scene_bridge.py` and invalid buffers rejected |
| scene camera identity | all 59 shipped episode names, camids and byte-equality flags match `scene_bridge.build()`; 58 identical files and `ESeries_055` camid 2 exception; bad blob, index, name and capacity rejected |
| EES container | all 1129 shipped files (720 cam, 409 car) match `ees_scene.parse_ees()`; short, unknown and inconsistent headers rejected |
| EES camera fields | all 31 named fields match `ees_fields.camera_fields()` on 255 shipped `CamData.EES` records; sentinel, short offset and null arguments rejected |
| EES frame lookup | all 14 shipped frame values match the `FUN_1401c8f60` last-match oracle; short buffer, overlong count and null input rejected |
| EES car_effect copy | all 40 native field copies match `ees_fields.CAR_EFFECT_COPY` on 32 records; short source/destination and null arguments rejected |
| EES type filter | 183600 shipped camera types across 720 files match the `FUN_1401ca060` type 0/2 rule |
| EES car_info | all 10800 shipped ids match the `0x8c` record words; short and null inputs rejected |
| EES car_disp | all 10800 shipped records match `ees_fields.car_disp_record()` including 896 non-finite yaw rows; NaN/Inf, short offset and null arguments rejected |
| String xrefs | all 195 names, 222 RVAs, duplicate-RVA groups and scan totals match `xrefs.json`; both find directions, bad blob, index, row, RVA and capacity rejected |
| .pdata stats | all 7 buckets and 20 largest functions match `pdata.json`; find, bad blob, index, row and capacity rejected |
| Reference words | all 98,805 words, 174,507 xrefs and 24,102 duplicate-RVA groups match `refs.json`; both find directions, bad blob, index, row and xref rejected |
| Enma sim facts | all 6 getters, 4 probe hits and 4096 config bytes match `enma_sim.json`; find, bad blob, index, row and capacity rejected |
| Path strings | all 1,271 executable and 422 source strings match `exe_paths.json`/`source_paths.json`; find, bad blob, index, group and capacity rejected |
| luaL_Reg tables | all 3 tables, 42 name/function rows and one code ref match `name_tables.json`; find, bad blob, index, row and capacity rejected |
| Name runs | all 521 runs, 13,283 names and 888 code refs match `name_tables.json`; name/user find, bad blob, index, row and capacity rejected |
| PE inventory | all 70,377 `.pdata` rows, 825 named/ordinal imports, 28 DLLs, 7 sections, 8 directories, 2 exports, PDB and provenance metadata match `pe.json`/`pdata.json`; RVA/directory/DLL/import find, all interior/gap RVA covers, bad blob, index, row and capacity rejected |
| Asset inventory | 2 roots, 32 extensions, 7 magics, 27 folders and 40 shader samples match `assets.json`; ext/magic/folder/shader find, bad blob, index and capacity rejected |
| Lua inventory | 2 roots, 158 dirs, all root counts, 1,252 defined names and all 215 native / 280 undefined top name/count pairs match `lua.json`; bad blob, root, kind, capacity and missing name rejected |
| Scene env | all 122 dirs, 59 present, 488 actor slots, 186 nonzero, 36 actor values and 26 stage values match shipped `Environment.Lua` files; bad blob, index and capacity rejected |
| Enma exports | all 172 mangled names and ordinals match `enma_api.json`; bad blob, index and capacity rejected |
| Enma defaults | all 32 structs, 89 fields and 2642 constant bytes match `enma_api.json`; struct/field find, bad blob, index and capacity rejected |
| Enma enums | all 16 domains and 1214 names/values match `enma_api.json`; find, bad blob, index, value and capacity rejected |
| Lua xrefs | 219 names, 222 function refs, 28 table refs, 65 table users and 60 duplicate-RVA groups match `bindings.json`; both find directions, bad blob, index and capacity rejected |
| honor schema | all 13 type names match the exe pointer table, 60 ordered fields and type-1 ABI offsets/PROPERTY slots/addresses match `STORY_NATIVE.md`; type/field find, bad blob, type, field and capacity rejected |
| Lua globals | all 219 names, call counts and 7 categories match `LUA_API.md`; find, bad blob, index and capacity rejected |
| context paths | 406 shipped car/model pairs match `contexts.context()`; bad set, index, name and capacity rejected |
| Environment.Lua | all 70 shipped files match `story_catalog.ENV_RE` and `as_int()`; comments, signs, malformed values and null inputs checked |
| native names | all 1036 names in 9 shipped pointer tables match PE reads and resolve through `find`; bad kind, index, blob and capacity rejected |
| scene config | 0x28 packing matches `scene_config.write_scene()`; all 408 shipped car/stage/day names resolve through `find`; three live eStage copies match `STORY_NATIVE.md` and the 26-value stage domain matches `scene_env_catalog`; bad blob, bad version, bad kind and short capacity rejected |
| stage-effect catalog | 6 shipped symbolic sounds read from the `R6STG` blob with matching set/symbol/file/tone name/wav, bank 3 tones 14/15, positions and loop flags; symbol lookup, bad magic and short blob checked |
| car catalog | 151 `PLC_*` specs packed to 70,764 bytes (version 4, 444-byte records), all fields, 151 `EngineSound` values and 906 cp932 text fields match Python; `PLC_928GT` found by model and id; legacy v1/v2/v3 and malformed blobs rejected |
| custom catalog | 250 colours, 107 wheels, 261 aero/parts, 151 tunes and 42 tire scales packed to 70,368 bytes; all five sections round-trip; malformed blobs rejected |
| story catalog | 122 episodes, 3,309 messages, 3,484 events and 647 `drive_story_*` keys packed to 386,681 bytes; sampled records and shared strings round-trip; all 15 summary fields match Python; malformed blobs rejected |
| native story keys | 101 hard-coded keys (1 direct, 100 table) match `wmn6r.exe` and all exist in msgdb.lua; exact lookup, source facts and malformed blobs checked |

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

- Recompiler (P1) still lacks indirect calls/host stubs and XMM/SIMD.
  `difftest.py --bounded` aligns the two `memcpy`-style contexts, so all 18
  sampled functions pass (16 random + 2 bounded); other loops still need
  per-function register ranges.
- BC1/BC2/BC3/ARGB8/A8R8G8B8 decode is in the C core and in
  `tools/engine/nut_texture.py`; GPU texture upload remains outside the core.
- `r6_glsl_pack_ubo()` writes reflected std140 members and
  `r6_glsl_texture_upload()` describes RGBA8 uploads for reflected sampler
  units; shader module creation and GPU calls stay outside the core.
- NDWD parser covers headers, groups, raw subrecords/chain records and strings;
  vertex layout selection, token semantics and native-consumed material chains
  stay unproven because every shipped chain record has flag zero.
- Physics is an original arcade model, not a trace-equivalent of Enma: the
  shipped DLL needs host state to initialise and cannot be driven standalone.
- Course descriptors are synthetic: no road mesh or checkpoint layout has been
  decoded from the dump yet. Race rules are not trace-equivalent of Enma.
- Rival cars, collision response, ghost/phantom and game systems (P5) not
  started.
