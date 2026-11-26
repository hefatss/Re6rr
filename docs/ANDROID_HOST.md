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
    adb push <dump> /sdcard/Android/data/com.wmmt.re6rr/files/dump

Open `platform/android` in Android Studio (AGP 8.5+, SDK 34, NDK required by
CMake). The app reads `cars.r6car`, the optional `custom.r6custom` and
`story.r6story`, every `*.r6course` in that directory, `glsl/bindings.r6glsl`
through `GlslBindings`, `glsl/vertex.r6gv` through `VertexLayout`,
`engine_sound.r6esnd` through `EngineSound`, `bgm.r6bgm` through
`BgmCatalog`, and `engine_runtime.r6ers` plus `engine_sound.r6esnd` through
`EngineRuntime`. `AssetProvider` uses the native gzip inflater; the core
still sees only bytes.

## UI

- `character car` overrides the model spinner through
  `CarCatalog.carIndexForCharacter()` — e.g. `CRC_928GT_Masaki`;
- load status shows customization colour/wheel counts and episode count when
  `custom.r6custom` / `story.r6story` are present.
- `course descriptor` selects the `.r6course` file.
- `throttle` toggles throttle/brake; `steer` is -1..1.
- Status shows game phase, race return code, odo, speed, gear, surface,
  offroad flag, lap and rival place.

`Game.selectCourse()` uses the descriptor list index as `course`, area `0`,
stage `3`; `Race` uses the same index with mode `4` (battle), one lap and a
3 s countdown. `GlslBindings` exposes record flags, UBO regions, sampler units
and RGBA8 upload descriptors from the compiled manifest, and packs std140
blocks from reflected region order, `Re6Texture` returns RGBA8 pixels from
inflated NTWD/NTLX containers, `Re6Audio` reads `.nub` bank metadata, tone
control fields and PCM bytes, `EngineSound` selects car/tune layer tones and
envelopes, `VertexLayout` reads vertex locations, semantics and masks, and
`BgmCatalog` resolves BGM ids and names, `EngineRuntime` evaluates the 16
layers using host libm, `VoiceRequest` builds and reads 0xa0 KeyOn records with
copied extension blobs, `Config3D` reads 3D sound sections, and `BankSetup`
`BankSetup` reads .nub registration views, `AudioStream` handles fade timing
and stream reservation, and `VoiceChain` copies chained-voice records; none
makes GL or audio-device calls. The
story catalog is data-only; no unlock progression, renderer, playback, mixer or
All.Net code exists.

## Validation

Desktop checks compile `Re6Engine.java`, `AssetProvider.java`,
`GlslBindings.java`, `Re6Texture.java`, `Re6Audio.java` and `EngineSound.java`
via `tools/engine/build_host.py`. `MainActivity.java` is
Android-only; its syntax
was checked against minimal local stubs under `build/tmp`. A real NDK/SDK
build remains unverified in this repository.
