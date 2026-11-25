"""Checks for the Environment.Lua -> native scene-config name resolution."""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import scene_config  # noqa: E402


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def fixtures():
    cars = ["PLC_NON"] + ["PLC_TEST%d" % index for index in range(1, 254)]
    stages = ["EAreaId_%d" % index for index in range(149)]
    days = ["Day_1", "NIGHT", "Day_2", "Day_3", "Day_4"]
    return {"cars": cars, "stages": stages, "days": days}


def run(dump, failures):
    tables = fixtures()
    check(scene_config.car_id_name(-1, tables["cars"]) == "PLC_NON",
          "car_id_name(-1)", failures)
    check(scene_config.car_id_name(253, tables["cars"]) == "PLC_TEST253",
          "car_id_name(253)", failures)
    check(scene_config.car_id_name(254, tables["cars"]) == "PLC_NON",
          "car_id_name(254)", failures)
    check(scene_config.stage_name(1, tables["stages"]) == "EAreaId_0",
          "stage_name(1)", failures)
    check(scene_config.stage_name(0, tables["stages"]) is None,
          "stage_name(0)", failures)
    check(scene_config.stage_name(150, tables["stages"]) is None,
          "stage_name(150)", failures)
    check(scene_config.day_name(1, tables["days"]) == "NIGHT",
          "day_name(1)", failures)
    check(scene_config.day_name(5, tables["days"]) is None,
          "day_name(5)", failures)

    values = {
        "actors": [5, 190, -1, 253], "stage": 43, "stage_root": 0,
        "stage_day": 1, "cam_id": 1,
    }
    scene = scene_config.write_scene(values)
    check(len(scene) == 0x28, "scene size", failures)
    check(struct.unpack_from("<i", scene, 0x08)[0] == 43, "stage slot", failures)
    check(struct.unpack_from("<i", scene, 0x10)[0] == 1, "day slot", failures)
    check(struct.unpack_from("<4i", scene, 0x14) == (5, 190, -1, 253),
          "actor slots", failures)
    check(struct.unpack_from("<i", scene, 0x24)[0] == 1, "cam slot", failures)

    resolved = scene_config.resolve(values, tables)
    check(resolved["actors"] == ["PLC_TEST5", "PLC_TEST190",
                                "PLC_NON", "PLC_TEST253"],
          "actor names", failures)
    check(resolved["stage"] == "EAreaId_42", "stage name", failures)
    check(resolved["stage_day"] == "NIGHT", "day name", failures)

    if dump:
        real, rows = scene_config.build(dump)
        check(len(real["cars"]) == 254, "shipped car table count", failures)
        check(real["cars"][5] == "PLC_NCEC", "shipped car 5", failures)
        check(real["cars"][144] == "PLC_A90", "shipped car 144", failures)
        check(real["cars"][190] == "CRC_Z31_Akio", "shipped car 190", failures)
        check(real["stages"][0] == "EAreaId_OsDojima",
              "shipped stage 0", failures)
        check(real["days"][1] == "NIGHT", "shipped day 1", failures)
        check(len(rows) > 0, "shipped episodes", failures)
        for row in rows:
            for name in row["resolved"]["actors"]:
                check(name.startswith(("PLC_", "CRC_", "OTH_")),
                      "actor name %s in %s" % (name, row["episode"]),
                      failures)
    return len(failures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    failures = []
    run(args.dump, failures)
    for failure in failures:
        print("FAIL " + failure)
    print("scene_config checks: %s" % ("FAIL" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
