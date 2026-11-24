# P5 — Car catalog

`tools/engine/car_catalog.py` builds a packed catalog from the 151 shipped
`data/car/specification/PLC_*_Specification.lua` files. Every script defines a
`CarDataList` table with the values the game uses for car selection and physics
setup. The tool reads those fields and writes a `.r6car` blob; no game data is
committed here.

    python tools/engine/car_catalog.py --dump D:\Games\W6W-05 \
        --out build\tmp\cars.r6car --report build\tmp\cars.json
    python tools/engine/car_catalog.py --list

The dump has 100 `getTirePos_CRC_*.lua` scripts and 95 `charCar/CRC_*`
directories, but no shipped `CRC_*` → `PLC_*` table. `car_mapping.py` derives
77 pairs from the name prefix before the first `_` and the four tire positions:
`CRC_928GT_Masaki` → `PLC_928GT`, `CRC_964_Shima` → `PLC_964T36`,
`CRC_R997_Ishida` → `PLC_R997`. `CRC_DC2_Tomoya` → `PLC_SE3P` comes from tire
geometry only. `CRC_DUMMY*`, `CRC_LOCAL_DUMMY`, `CRC_AIRPORT_BUS` and
`CRC_SEASIDE_TRUCK` stay unmapped. Every JSON report row records its method
and RMS distance in source decimetres; these are derived, not shipped facts.

## Packed layout

Little endian, 24-byte header, car records then mapping records:

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | magic `R6CAR\0\1\0` |
| 8 | 4 | version `2` (`1` = no mappings) |
| 12 | 4 | car record count |
| 16 | 4 | record size `144` |
| 20 | 4 | mapping count |
| 24 | 24 | `model`, e.g. `PLC_928GT` |
| 48 | 64 | display name from `CarDataNameUS_1/2` or Japanese fallback |
| 112 | 24 | `CarMakerName` |
| 136 | 2 | `ModelID` |
| 138 | 2 | `VisualModelID` |
| 140 | 2 | `Horsepower1st` |
| 142 | 2 | `EngineDisplacement` |
| 144 | 1 | `DriveSystem` |
| 145 | 1 | `MissionNumber` |
| 146 | 1 | flags: dress-up, custom colour, supercharger |
| 147 | 1 | low byte of `MakerID` |
| 148 | 4 | `TireOutsideFront` |
| 152 | 4 | `TireOutsideRear` |
| 156 | 4 | `PureTireWidthFront` |
| 160 | 4 | `PureTireWidthRear` |
| 164 | 4 | `MakerID` |

Mapping records are 48 bytes each and follow all car records:

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 24 | `CRC_*` character-car name |
| 24 | 24 | mapped `PLC_*` model |

Strings are CP932 bytes if the source script is CP932, otherwise UTF-8 bytes
re-encoded to CP932; names are truncated at 63 bytes. The largest shipped name
is 56 bytes.

## C API

`engine/include/r6/r6_car.h` and `engine/src/game/car.c` provide:

- `r6_car_catalog_parse()` — validates magic, version, record size and total
  size, then copies records into caller storage. `R6_ERR_BUFFER` reports the
  required capacity, matching the `.r6course` and gzip conventions.
- `r6_car_catalog_find_model()` / `r6_car_catalog_find_id()` — bounded lookups.
- `r6_car_catalog_character_count()` / `r6_car_catalog_find_character()` —
  raw-blob reads of the mapping section; a hit returns the car index.

JNI exposes `Re6Engine.CarCatalog` with `count()`, `model(index)`,
`info(index)`, `characterCount()`, `carIndexForCharacter(name)` and
`modelForCharacter(name)`. The numeric array is
`modelId visualId horsepower cc drive mission flags tireFront tireRear
widthFront widthRear`.

## Validation

`python tools/engine/test_catalog.py` checks all 151 records against the Python
generator, finds `PLC_928GT` by both model code and `ModelID` 120, resolves
three character cars, and rejects truncated data, bad magic, a bad record
size, a bad mapping count, an empty blob and short capacity. Result: 151 cars,
77 mappings, 25,464 bytes, 16 makers.

## Gaps

- Mappings are inferred, not shipped; `CRC_DC2_Tomoya` has tire-only evidence.
- No colour list, aero parts or wheel catalog.
- `DriveSystem` values above 3 appear in the dump; the catalog preserves them
  but the vehicle model still only defines FR/RR/MR/4WD.
