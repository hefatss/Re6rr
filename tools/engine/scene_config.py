"""Resolve Environment.Lua fields through shipped native name tables.

    python tools/engine/scene_config.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/scene_config.json

Native chain, all addresses VA in `wmn6r.exe` (image base 0x140000000):

  0x1401c7870  GetActor0..3 / GetStage* / GetCamid -> 8-slot struct
  0x1401c8050  wrapper: scene struct = param_1 + 8
  0x1401e3640  copies slots to scene struct +0x08..+0x24
  0x1401fae70  logs "Stage:", "root:", "car1:".."car4:"
  0x1401d1db0  stage-1 -> EAreaId_* table at 0x141c65a90 (149 entries)
  0x1401d1d00  day -> Day_*/NIGHT table at 0x141c65738 (5 entries)
  0x1401d1d20  actor -> getCarIdName -> PLC/CRC table at 0x141c533c0 (254)

`getCarIdName` is 0x1400c4830: -1 -> "PLC_NON", 0..253 index the table,
anything else logs `getCarIdName(): CAR_ID err [%d]` and returns "PLC_NON".
The scene logger is a debug display, not rival instantiation; gameplay car
assignment stays a separate native decision.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))
from pe_report import PE  # noqa: E402

sys.path.insert(0, HERE)
import story_catalog  # noqa: E402

CAR_NAMES_VA = 0x141C533C0
CAR_NAMES_COUNT = 254
STAGE_NAMES_VA = 0x141C65A90
STAGE_NAMES_COUNT = 149
DAY_NAMES_VA = 0x141C65738
DAY_NAMES_COUNT = 5

# 0x1401e3640: environment slot -> scene struct offset (int32 fields)
SLOT_OFFSETS = {
    "stage": 0x08,
    "stage_root": 0x0C,
    "stage_day": 0x10,
    "cam_id": 0x24,
}
ACTOR_OFFSETS = (0x14, 0x18, 0x1C, 0x20)
SCENE_SIZE = 0x28

SCENE = os.path.join("data_jp", "scene")


def pointer_names(pe, va, count):
    off = pe.off(va - pe.image_base)
    if off is None:
        raise ValueError("name table VA 0x%x is not mapped" % va)
    pointers = struct.unpack_from("<%dQ" % count, pe.raw, off)
    names = []
    for pointer in pointers:
        name = pe.cstr(pointer - pe.image_base)
        if name is None:
            raise ValueError("name pointer 0x%x is not a string" % pointer)
        names.append(name)
    return names


def name_tables(pe):
    return {
        "cars": pointer_names(pe, CAR_NAMES_VA, CAR_NAMES_COUNT),
        "stages": pointer_names(pe, STAGE_NAMES_VA, STAGE_NAMES_COUNT),
        "days": pointer_names(pe, DAY_NAMES_VA, DAY_NAMES_COUNT),
    }


def car_id_name(value, cars):
    """0x1400c4830: -1 and out-of-range both return PLC_NON."""
    if value == -1 or not 0 <= value < len(cars):
        return "PLC_NON"
    return cars[value]


def stage_name(value, stages):
    """0x1401d1db0 is called with `stage - 1` by the scene logger."""
    index = value - 1
    if not 0 <= index < len(stages):
        return None
    return stages[index] or None


def day_name(value, days):
    """0x1401d1d00 is called with the raw STAGE_DAY value."""
    if not 0 <= value < len(days):
        return None
    return days[value]


def write_scene(values):
    """Model 0x1401e3640: pack environment slots into the 0x28-byte struct."""
    data = bytearray(SCENE_SIZE)
    for key, offset in SLOT_OFFSETS.items():
        struct.pack_into("<i", data, offset, values[key])
    for offset, actor in zip(ACTOR_OFFSETS, values["actors"]):
        struct.pack_into("<i", data, offset, actor)
    return bytes(data)


def resolve(values, tables):
    cars, stages, days = tables["cars"], tables["stages"], tables["days"]
    return {
        "actors": [car_id_name(value, cars) for value in values["actors"]],
        "stage": stage_name(values["stage"], stages),
        "stage_root": values["stage_root"],
        "stage_day": day_name(values["stage_day"], days),
        "cam_id": values["cam_id"],
    }


def build(dump):
    pe = PE(os.path.join(dump, "wmn6r.exe"))
    tables = name_tables(pe)
    root = os.path.join(dump, SCENE)
    rows = []
    for entry in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        path = os.path.join(root, entry)
        if not os.path.isdir(path) or not entry.startswith("ESeries_"):
            continue
        values = story_catalog.parse_environment(path)
        if not values["present"]:
            continue
        scene = write_scene(values)
        rows.append({
            "episode": entry,
            "values": values,
            "resolved": resolve(values, tables),
            "scene": scene.hex(),
        })
    return tables, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", help="write JSON report")
    args = parser.parse_args()

    tables, rows = build(args.dump)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf8") as stream:
            json.dump({
                "tables": {key: len(value) for key, value in tables.items()},
                "episodes": rows,
            }, stream, indent=2, ensure_ascii=False)
    print("name tables: cars %d, stages %d, days %d" %
          (len(tables["cars"]), len(tables["stages"]), len(tables["days"])))
    print("episodes: %d" % len(rows))
    for row in rows[:5]:
        print("  %-12s %s | %s | %s" %
              (row["episode"], row["resolved"]["actors"],
               row["resolved"]["stage"], row["resolved"]["stage_day"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
