# Android host

`platform/android` is a minimal Android Gradle project around the freestanding
engine. It has no renderer and no game data. It loads the Lua context for one
car, steps `Vehicle` + `Race` + `Game` at 60 Hz and prints telemetry.

    platform/android/
      settings.gradle
      build.gradle
      app/build.gradle              # CMake points at ../../../CMakeLists.txt
      app/src/main/AndroidManifest.xml
      java/com/wmmt/re6rr/...        # bridge + MainActivity

## Setup

Generate derived assets from your own dump, then push them with the `data/`
tree to app external files:

    python tools/engine/car_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/cars.r6car
    python tools/engine/custom_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/custom.r6custom
    python tools/engine/story_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/story.r6story
    python tools/engine/course_descriptor.py --dump D:\Games\W6W-05 \
        --route FUKUOKA --out <dump>/FUKUOKA.r6course
    python tools/engine/nsxr_shader.py --dump D:\Games\W6W-05 \
        --glsl-dir <dump>/glsl
    python tools/engine/vertex_layout.py \
        --manifest <dump>/glsl/manifest.json --out <dump>/glsl/vertex.r6gv
    python tools/engine/bgm_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/bgm.r6bgm
    python tools/engine/engine_runtime_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/engine_runtime.r6ers
    python tools/engine/stage_effect_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/stage_effect.r6stg
    python tools/engine/scene_config_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/scene_config.r6scn
    python tools/engine/native_names_catalog.py --dump D:\Games\W6W-05 \
        --out <dump>/native_names.r6nam
    python tools/engine/lua_globals_catalog.py \
        --out <dump>/lua_globals.r6lua
    python tools/engine/lua_xref_catalog.py \
        --out <dump>/lua_xrefs.r6xrf
    python tools/engine/lua_inventory_catalog.py \
        --out <dump>/lua_inventory.r6lsi
    python tools/engine/asset_inventory_catalog.py \
        --out <dump>/asset_inventory.r6aiv
    python tools/engine/pe_inventory_catalog.py \
        --out <dump>/pe_inventory.r6pei
    python tools/engine/reloc_inventory_catalog.py \
        --out <dump>/reloc_inventory.r6rlc
    python tools/engine/gz_effect_catalog.py \
        --out <dump>/gz_effect.r6gef
    python tools/engine/xmlt_lists_catalog.py \
        --out <dump>/xmlt_lists.r6xlt
    python tools/engine/msgdb_namespace_catalog.py \
        --out <dump>/msgdb_namespace.r6mns
    python tools/engine/shader_param_catalog.py \
        --out <dump>/shader_params.r6shp
    python tools/engine/wmbk_bank_catalog.py \
        --out <dump>/wmbk_bank.r6wbk
    python tools/engine/filter_dictionary_catalog.py \
        --out <dump>/filter_dictionary.r6flt
    python tools/engine/nut_file_catalog.py \
        --out <dump>/nut_files.r6ntf
    python tools/engine/default_ghost_catalog.py \
        --out <dump>/default_ghost.r6gh
    python tools/engine/enma_error_log_catalog.py \
        --out <dump>/enma_error_log.r6elm
    python tools/engine/ghost_region_catalog.py \
        --out <dump>/ghost_region.r6grl
    python tools/engine/tga_inventory_catalog.py \
        --out <dump>/tga_inventory.r6tga
    python tools/engine/street_lamp_catalog.py \
        --out <dump>/street_lamp.r6slp
    python tools/engine/name_runs_catalog.py \
        --out <dump>/name_runs.r6ntr
    python tools/engine/lua_reg_tables_catalog.py \
        --out <dump>/lua_reg_tables.r6lreg
    python tools/engine/path_strings_catalog.py \
        --out <dump>/path_strings.r6pst
    python tools/engine/enma_sim_catalog.py \
        --out <dump>/enma_sim.r6esim
    python tools/engine/ref_words_catalog.py \
        --out <dump>/ref_words.r6ref
    python tools/engine/pdata_stats_catalog.py \
        --out <dump>/pdata_stats.r6pds
    python tools/engine/string_xrefs_catalog.py \
        --out <dump>/string_xrefs.r6sxr
    python tools/engine/enma_enum_catalog.py \
        --out <dump>/enma_enums.r6eme
    python tools/engine/enma_defaults_catalog.py \
        --out <dump>/enma_defaults.r6edf
    python tools/engine/enma_exports_catalog.py \
        --out <dump>/enma_exports.r6eex
    python tools/engine/scene_env_catalog.py \
        --dump <dump> --out <dump>/scene_env.r6ses
    python tools/engine/honor_schema_catalog.py \
        --out <dump>/honor_schema.r6hon
    adb push <dump> /sdcard/Android/data/com.wmmt.re6rr/files/dump

Open `platform/android` in Android Studio (AGP 8.5+, SDK 34, NDK required by
CMake). The app reads `cars.r6car`, the optional `custom.r6custom` and
`story.r6story`, `story_keys.r6sk`, every `*.r6course` in that directory, `glsl/bindings.r6glsl`
through `GlslBindings`, `glsl/vertex.r6gv` through `VertexLayout`,
`engine_sound.r6esnd` through `EngineSound`, `bgm.r6bgm` through
`BgmCatalog`, `stage_effect.r6stg` through `StageEffect`,
`scene_config.r6scn` through `SceneConfig`, `native_names.r6nam` through
`NativeNames`, and `engine_runtime.r6ers` plus `engine_sound.r6esnd` through `EngineRuntime`.
`Re6Container` exposes inflated XMD.001 streams so `.tex` streams can be passed
to `Re6Texture` and `.mdl` streams to `Re6MeshRecords`.
`AssetProvider` uses the native gzip inflater; the core
still sees only bytes.

## UI

- `character car` overrides the model spinner through
  `CarCatalog.carIndexForCharacter()` — e.g. `CRC_928GT_Masaki`;
- `CarCatalog.name()` / `maker()` and v4 `nameJp()`, `carName()`, `glade()`,
  `year()` decode cp932 text from `.r6car`;
  `indexForModel()` / `indexForId()` reuse the C exact lookups;
  the spinner still uses raw `PLC_*` codes;
- `CarCatalog.engineSound()` supplies the verbatim `EngineSound` value needed
  by `EngineSound.find()`; the current spinner does not yet call it;
- `CustomCatalog.tuneIndexForModel()` resolves a selected `PLC_*` model to the
  151-row per-car tune record; no UI wiring was added;
- `StoryCatalog.summary()` returns 15 raw phase/kind/flag counts from
  `story.r6story`; the UI still shows only the episode count;
- `StoryKeyNamespace` exposes all 647 shipped `drive_story_` MessageIDs with
  101 observed native sources and 546 message-DB-only names;
- `StoryKeys` exposes the 101 keys hard-coded by the executable and their
  direct/table source; no UI behaviour depends on it yet;
- `LoadlistCatalog` exposes 76 LOADLIST files, 343 section blocks and 17,163
  NDWD stream descriptors; geometry and surface classes are not copied;
- `CoursePaths` exposes 33 route rows, 143 exact `.bin` refs and 178 path-bin
  sizes/triples; duplicate basenames are not resolved;
- `XmdAssets` exposes 1860 `.TEX`/`.MDL` XMD.001 header facts and 28,863 stream
  offsets/sizes; stream contents are not copied;
- `EesInventory` exposes 1129 `.EES` paths, header facts and 2667 array facts;
  array contents are not copied;
- `MtmpTables` exposes 34 `.MTMP` scales and 286 raw object lines; no transform
  semantics are inferred;
- `NufHeaders` exposes 22 `.NUF` paths, file sizes and raw 64-byte prefixes;
  glyph tables are not interpreted;
- `LmdCatalog` exposes 985 `.LMD` gzip/XMD header facts and three stream sizes
  per file; payloads are not inflated by the core;
- `ActHeaders` exposes 170 `.ACT` paths, file sizes and raw 64-byte prefixes;
  no actor or animation semantics are inferred;
- `MedHeaders` exposes 67 validated `.MED` 0x100 headers, frame counts and
  paths; frame data is not interpreted;
- load status shows customization colour/wheel counts and episode count when
  `custom.r6custom` / `story.r6story` are present.
- `course descriptor` selects the `.r6course` file.
- `throttle` toggles throttle/brake; `steer` is -1..1.
- Status shows game phase, race return code, odo, speed, gear, surface,
  offroad flag, lap and rival place.

`Game.selectCourse()` uses the descriptor list index as `course`, area `0`,
stage `3`; `Race` uses the same index with mode `4` (battle), one lap and a
3 s countdown. `GlslBindings` exposes shipped GLES lowering totals (20,563
instructions in 43 opcodes), record flags, UBO regions, sampler units
and RGBA8 upload descriptors from the compiled manifest, and packs std140
blocks from reflected region order, `NshContainer` validates shipped NSXR
headers and DXBC chunk tables and returns the 29 summed STAT fields, 23 summed
RDEF fields, 7 SHDR operand/modifier totals, 7 ISGN/OSGN totals and one creator
string, `ShaderControlFlow` resolves the 303 shipped
structured SM4 blocks by shader/stage with case and break/continue spans, `ShaderUsage`
resolves reflected uniforms and texture/sampler keys with operand counts per stage,
`Re6Texture` exposes the 11 NTWD/NTLX file-level header fields, derives mip
payload layout and returns RGBA8 pixels from inflated containers, `Re6Audio` reads `.nub` bank metadata, tone
control fields, four getter user parameters, codec-1 total samples, opaque
registration bytes and PCM bytes, `EngineSound` selects car/tune layer tones and
envelopes, `VertexLayout` reads vertex locations, semantics and masks, and
`BgmCatalog` resolves BGM ids and names, `ContextPaths` returns the ordered
Lua bundle paths, `lua_globals.r6lua` through `LuaGlobals`, `lua_xrefs.r6xrf` through
`LuaXrefs`, `lua_inventory.r6lsi` through `LuaInventory`, `asset_inventory.r6aiv` through `AssetInventory`, `pe_inventory.r6pei` through `PeInventory`, `reloc_inventory.r6rlc` through `RelocInventory`, `gz_effect.r6gef` through `GzEffectCatalog`, `xmlt_lists.r6xlt` through `XmltLists`, `msgdb_namespace.r6mns` through `MsgdbNamespace`, `shader_params.r6shp` through `ShaderParamCatalog`, `wmbk_bank.r6wbk` through `WmbkBankCatalog`, `filter_dictionary.r6flt` through `FilterDictionaryCatalog`, `nut_files.r6ntf` through `NutFileCatalog`, `default_ghost.r6gh` through `DefaultGhostCatalog`, `enma_error_log.r6elm` through `EnmaErrorLogCatalog`, `ghost_region.r6grl` through `GhostRegionCatalog`, `tga_inventory.r6tga` through `TgaInventoryCatalog`, `street_lamp.r6slp` through `StreetLampCatalog`, `name_runs.r6ntr` through `NameRuns`, `lua_reg_tables.r6lreg` through `LuaRegTables`, `path_strings.r6pst` through `PathStrings`, `enma_sim.r6esim` through `EnmaSimFacts`, `ref_words.r6ref` through `RefWords`, `pdata_stats.r6pds` through `PdataStats`, `string_xrefs.r6sxr` through `StringXrefs`, `lmd.r6lmd` through `LmdCatalog`, `nuf_headers.r6nuf` through `NufHeaders`, `mtmp.r6mtmp` through `MtmpTables`, `ees_inventory.r6ees` through `EesInventory`, `xmd_assets.r6xas` through `XmdAssets`, `course_paths.r6cps` through `CoursePaths`, `loadlist.r6lls` through `LoadlistCatalog`, `story_key_namespace.r6skn` through `StoryKeyNamespace`, `act_headers.r6act` through `ActHeaders`, `med_headers.r6med` through `MedHeaders`, `enma_enums.r6eme` through `EnmaEnums`, `enma_defaults.r6edf`
through `EnmaDefaults`, `enma_exports.r6eex` through `EnmaExports`, `scene_env.r6ses` through
`SceneEnvStats`, `honor_schema.r6hon` through `HonorSchema`, `EngineRuntime` evaluates the 16
layers using host libm, `EngmapTable` reads the 320 sound/group pairs, `EmtisTable` reads EMTIS
sections, prefix counts and 416 source WAV names with exact-name lookup,
`VoiceRequest` builds and reads 0xa0 KeyOn records with
copied extension blobs, `Config3D` reads and validates 3D sound sections, `BankSetup` reads
.nub registration views, `AudioStream` handles fade timing and stream
reservation, `VoiceChain` copies chained-voice records and applies core fields,
`SoundInit` validates the Sound::Initialize config and reports the shipped Impl tail constants, `BgmFade` reads and updates
stream fade state, `BgmManager` applies playBGM id dispatch, `SoundDispatch`
copies bank/loop/positional SE records, `SoundConfig` parses config.bin,
`BankSlots` finds free registration slots, `SoundStrings` finds bank/tone
names and WAV paths, `LuaAudioBindings` reads the twelve Lua binding rows,
`CourseSurface` classifies road names, `CoursePaths` exposes 33 route rows,
143 exact `.bin` refs and 178 path bins, `LoadlistCatalog` exposes 76 LOADLIST
files, 343 section blocks and 17163 NDWD stream descriptors, `SceneBridge` copies camid, resolves
camera containers/records and reads the 59-episode camera-file identity map,
`EesContainer` parses shipped headers, `EesCamera` reads named fields, filters type 0/2 and resolves frames with
last-match semantics, `EesCarInfo` reads car ids, `EesCarEffect` copies the 40 runtime
fields, `EesCarDisp` reads display records, `AudioLayoutFacts` exposes bank/voice table offsets, `VoiceDispatchFacts`
exposes recovered status codes, call sites and three KeyOn user groups, `VoiceCoreTableFacts` exposes the
192-entry lookup layout,
`ContextPaths` returns ordered Lua bundle paths, `LuaGlobals` exposes shipped global call sites, `LuaXrefs` maps names to native refs and resolves an RVA to every location using it, `LuaInventory` counts 158 Lua directories and resolves 1,252 defined plus 495 top name/count rows, `AssetInventory` reads 32 extensions and 27 folders, `PeInventory` reads 70,377 `.pdata` rows, 825 imports, 8 PE directories and exe SHA-256/path provenance, `RelocInventory` reads 1,833 relocation blocks and 270,128 entries with section ownership and type counts, `GzEffectCatalog` reads 1,087 gzip headers, ISIZE facts and 16-byte inflated prefixes, `XmltLists` reads 591 files, 3,482 lists, 4,432 seeds and field-tag references, `MsgdbNamespace` reads all 31,021 MessageIDs, byte offsets and 58 groups, `ShaderParamCatalog` reads 142 shader Lua paths, model names and 8 float32 values, `WmbkBankCatalog` reads 20 root banks and 22 WMBK records, `FilterDictionaryCatalog` reads 17 filter Lua files and 6,493 row shapes, `NutFileCatalog` reads 11,151 `.nut` file-level headers, `DefaultGhostCatalog` reads 9 ghost tables and 69,056 stride-136 records, `EnmaErrorLogCatalog` reads 6 error logs and 4,010 CRLF lines, `GhostRegionCatalog` reads 7 Lua files and 329 region rows, `TgaInventoryCatalog` reads 8 TGA headers, `StreetLampCatalog` reads 168 lamp tables, `NameRuns` reads 521 pointer runs, 13,283 names and all code refs for an RVA, `LuaRegTables` reads 3 `luaL_Reg` tables with 42 rows and resolves function RVAs to every row, `PathStrings` reads 1,693 exe/source path strings, `EnmaSimFacts` reads 6 input getters and 4096 config bytes, `RefWords` reads 98,805 words, 174,507 xrefs and all reverse RVA hits, `PdataStats` reads 7 size buckets and 20 largest functions, `StringXrefs` reads 195 raw string xrefs, scan totals and all reverse RVA hits, `EnmaEnums` exposes 16 enum domains and resolves values to every ordinal, `EnmaDefaults` copies 32 SetDefault layouts, `EnmaExports` resolves 172 DLL symbols, `SceneEnvStats` inventories 122 scene directories, `HonorSchema` reads the predicate schema and type-1 native ABI offsets, `EnvironmentLua` parses scene scripts, `NativeNames` resolves shipped pointer
names, `SceneConfig` packs scenes, resolves native names and reports the three live eStage copies, and
`StageEffect` resolves shipped symbolic sounds to bank/tone; none makes GL or
audio-device calls. The
story catalog is data-only; no unlock progression, renderer, playback, mixer or
All.Net code exists.

## Validation

Desktop checks compile `Re6Engine.java`, `AssetProvider.java`,
`GlslBindings.java`, `NshContainer.java`, `ShaderControlFlow.java`, `ShaderUsage.java`, `EngmapTable.java`, `EmtisTable.java`, `NativeNames.java`, `ContextPaths.java`, `LuaGlobals.java`, `LuaXrefs.java`, `LuaInventory.java`, `AssetInventory.java`, `PeInventory.java`, `RelocInventory.java`, `GzEffectCatalog.java`, `XmltLists.java`, `MsgdbNamespace.java`, `ShaderParamCatalog.java`, `WmbkBankCatalog.java`, `FilterDictionaryCatalog.java`, `NutFileCatalog.java`, `DefaultGhostCatalog.java`, `EnmaErrorLogCatalog.java`, `GhostRegionCatalog.java`, `TgaInventoryCatalog.java`, `StreetLampCatalog.java`, `NameRuns.java`, `LuaRegTables.java`, `PathStrings.java`, `EnmaSimFacts.java`, `RefWords.java`, `PdataStats.java`, `StringXrefs.java`, `LmdCatalog.java`, `NufHeaders.java`, `MtmpTables.java`, `EesInventory.java`, `XmdAssets.java`, `CoursePaths.java`, `LoadlistCatalog.java`, `StoryKeyNamespace.java`, `ActHeaders.java`, `MedHeaders.java`, `EnmaEnums.java`, `EnmaDefaults.java`, `EnmaExports.java`, `SceneEnvStats.java`, `HonorSchema.java`, `Re6Texture.java`, `Re6Container.java`,
`Re6MeshRecords.java`, `Re6Audio.java` and `EngineSound.java`
via `tools/engine/build_host.py`. `MainActivity.java` is
Android-only; its syntax
was checked against minimal local stubs under `build/tmp`. A real NDK/SDK
build remains unverified in this repository.
