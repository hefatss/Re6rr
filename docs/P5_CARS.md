# P5 — Car catalog

`tools/engine/car_catalog.py` builds a packed catalog from the 151 shipped
`data/car/specification/PLC_*_Specification.lua` files. Every script defines a
`CarDataList` table with the values the game uses for car selection and physics
setup. The tool reads those fields and writes a `.r6car` blob; no game data is
committed here.

    python tools/engine/car_catalog.py --dump D:\Games\W6W-05 \
        --out build\tmp\cars.r6car --report build\tmp\cars.json
    python tools/engine/car_catalog.py --list

The dump also contains 95 `charCar/CRC_*` directories. They are listed in the
JSON report but not tied to a model: no shipped table maps a character car to
its `PLC_*` specification. `tools/engine/contexts.py` still needs that pair
passed in explicitly.

## Packed layout

Little endian, 24-byte header then 144-byte records:

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | magic `R6CAR\0\1\0` |
| 8 | 4 | version `1` |
| 12 | 4 | record count |
| 16 | 4 | record size `144` |
| 20 | 4 | reserved |
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

Strings are CP932 bytes if the source script is CP932, otherwise UTF-8 bytes
re-encoded to CP932; names are truncated at 63 bytes. The largest shipped name
is 56 bytes.

## C API

`engine/include/r6/r6_car.h` and `engine/src/game/car.c` provide:

- `r6_car_catalog_parse()` — validates magic, version, record size and total
  size, then copies records into caller storage. `R6_ERR_BUFFER` reports the
  required capacity, matching the `.r6course` and gzip conventions.
- `r6_car_catalog_find_model()` / `r6_car_catalog_find_id()` — bounded lookups.

JNI exposes `Re6Engine.CarCatalog` with `count()`, `model(index)` and
`info(index)`; the numeric array is
`modelId visualId horsepower cc drive mission flags tireFront tireRear
widthFront widthRear`.

## Validation

`python tools/engine/test_catalog.py` checks all 151 records against the Python
generator, finds `PLC_928GT` by both model code and `ModelID` 120, and rejects
truncated data, bad magic, a bad record size, an empty blob and short capacity.
Result: 151 records, 21,768 bytes, 16 makers.

## Gaps

- No character-car → model mapping, colour list, aero parts or wheel catalog.
- `DriveSystem` values above 3 appear in the dump; the catalog preserves them
  but the vehicle model still only defines FR/RR/MR/4WD.
