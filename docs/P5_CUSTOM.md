# P5 — Customization catalog

`tools/engine/custom_catalog.py` derives one packed `.r6custom` blob from the
dump. No game data is committed; the tool reads the player's own files.

    python tools/engine/custom_catalog.py --dump D:\Games\W6W-05 \
        --out build\tmp\custom.r6custom --report build\tmp\custom.json

## Evidence

- `data/car/color/LibraryColor.lua` declares `COLOR_MAX = 250`, `ColorNameList`
  and 250 `ColorList` entries with `ListVec4`, `ListFloat` and `ListInt` blocks.
- `data_jp/msgdb/msgdb.lua` holds `custom_color_000..240`. The library-ID to
  message-ID offset is confirmed by `PLC_AE86_CustomColor.lua:77-100`:
  library `type83` maps to `custom_color_082`. Library `type0` has no label.
- `docs/recon/name_tables.json` tables at `0x1c57dd8` and `0x1c581e0` hold the
  ordered `SWH_*` and `CAR_PARTS_ID_*` names recovered from the executable.
- `data/car/tire/script/TireDefine.lua` defines `WHEEL_SCALE_INC_13..22`,
  `TIRE_WIDTH_SCALE_155..355` and the 12 `TIRE_OUTER_DIAMETER` values.
- `data/car/specification/PLC_*_Specification.lua` carries `AeroCategoryID`,
  `HaveWingA..H`, `HaveWingN_A..N`, `HaveCustomGTWing`, wheel inches and the
  11 default/40 custom colour IDs. Values come from the same 151 `data/`
  specs used by the car catalog.

## Packed layout

Little endian. Header is 32 bytes:

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | magic `R6CUS\0\1\0` |
| 8 | 4 | version `1` |
| 12 | 4 | colour count |
| 16 | 4 | wheel count |
| 20 | 4 | aero/parts count |
| 24 | 4 | per-car tune count |
| 28 | 4 | tire-scale count |

Sections follow in that order. All strings are NUL-padded; colour names are
CP932, all others ASCII.

| Section | Record | Contents |
| --- | --- | --- |
| colour | 96 B | `id icon feel pad`, `body0[4]`, `body1[4]`, `spec[4]`, `params[4]`, `name[24]` |
| wheel | 48 B | `id pad`, `name[24]`, `flags`, reserved |
| aero | 64 B | `id pad`, `name[48]`, `flags`, reserved |
| tune | 160 B | `model[24]`, aero/limited/wheel/wing fields, 11 default IDs, 40 custom IDs, car flags |
| tire | 8 B | `kind`, `index`, `value` |

Wheel `flags` has bit 1 when a matching `SWH_*.mdl` asset exists. Aero flags
mark the name category: aero 1, wing 2, bonnet 4, spoiler 8, diffuser 16,
skirt 32, wheel slot 64. Tire kinds are 0 wheel scale, 1 width scale,
2 outer diameter.

## C API

`engine/include/r6/r6_custom.h` and `engine/src/game/custom.c` provide a
validate-then-view parser. `r6_custom_catalog_parse()` checks magic, version,
counts and exact size, then returns typed section pointers. Record accessors
copy into caller storage, so unaligned host buffers stay safe. Lookups exist
for colour ID, wheel name, aero name and car model. Unknown names return `-1`.

## JNI

`Re6Engine.CustomCatalog` wraps the blob on Android. `counts()` are section
sizes in colour/wheel/aero/tune/tire order. `color(index)` returns
`id icon feel body0[4] body1[4] spec[4] params[4]`; `colorName(index)` decodes
the CP932 message-DB label. `wheelName`, `wheelFlags`, `aeroName`,
`aeroFlags`, `tuneModel`, `tune` and `tire` expose the remaining sections.
`tuneIndexForModel()` resolves a `PLC_*` model to its tune index using the same
exact-match C lookup as the ctypes test; unknown models return `-1`.
`tune()` returns 10 scalar fields followed by 11 default and 40 custom colour
IDs. Java only owns the byte array; the native layer validates and copies
fixed-size records.

## Validation

`python tools/engine/test_custom_catalog.py` checks all five section counts,
ctypes record sizes, sampled records from each section, name/lookups and
malformed blobs. `build_host.py --test` also syntax-checks the JNI layer and
compiles the Java bridge. Result: 250 colours, 107 wheels, 261 aero/parts
names, 151 per-car tunes, 42 tire scales, 70,368 bytes.

## Gaps

- No human-readable aero or wheel labels ship in plain text. Their menu text is
  gzip-compiled NTLX under `data_jp/menu`, so only part IDs are catalogued.
- `AeroCategoryID` values are only `0`, `3` and `300`; no local table maps them
  to concrete body kits.
- Six cars disagree on default-colour count between the spec and the per-car
  `*_DefaultColor.lua`; the catalog keeps the spec IDs.
- `data_jp/car/specification/PLC_MA61_Specification.lua` is not in the car
  catalog's 151-spec set, so no tune record is emitted for it.
- Online/DLC-only parts are absent from this dump.
