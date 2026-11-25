"""Checks the Environment.Lua camid -> .EES camera slot bridge."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import scene_bridge as sb  # noqa: E402
import scene_config  # noqa: E402


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def run(dump, failures):
    check(sb.CONFIG_OFFSET == 0x740 and sb.CONFIG_CAMID == 0x70,
          "config offset", failures)
    check(sb.CONTAINER_BASE == 0x2D78 and sb.CONTAINER_STRIDE == 0x1B0,
          "camera container layout", failures)
    check(sb.LOADER_CAMID == 0x48, "loader camid offset", failures)
    check([sb.container_offset(i) for i in range(5)] ==
          [0x2D78, 0x2F28, 0x30D8, 0x3288, 0x3438],
          "camera container offsets", failures)

    scene = bytearray(scene_config.SCENE_SIZE)
    config = bytearray(0x800)
    for camid in (0, 1, 2, 0xFF):
        scene[scene_config.SLOT_OFFSETS["cam_id"]:
              scene_config.SLOT_OFFSETS["cam_id"] + 4] = camid.to_bytes(
                  4, "little", signed=True)
        copied = sb.write_camid(scene, config)
        check(copied == camid, "copied camid", failures)
        check(int.from_bytes(config[sb.CONFIG_CAMID:sb.CONFIG_CAMID + 4],
                             "little", signed=True) == camid,
              "config camid", failures)
        if camid < 5:
            check(sb.container_offset(camid) ==
                  sb.CONTAINER_BASE + camid * sb.CONTAINER_STRIDE,
                  "slot arithmetic", failures)
    try:
        sb.container_offset(5)
        failures.append("camera slot bound")
    except ValueError:
        pass

    records = [
        {"type": 2, "start": 100, "end": 120, "exact": 0},
        {"type": 2, "start": 110, "end": 130, "exact": 0},
        {"type": -1, "start": -1, "end": None, "exact": 1},
    ]
    check(sb.runtime_camera_at_frame(records, 115) == 0,
          "runtime first match", failures)
    check(ees_fields.camera_at_frame(records, 115) == 1,
          "scene last match", failures)
    check(sb.runtime_camera_at_frame(records, 200) == -1,
          "runtime miss", failures)

    rows = sb.build(dump)
    check(len(rows) == 59, "episode count", failures)
    check(all(row["copied_camid"] == row["cam_id"] == row["config_camid"]
              for row in rows), "shipped bridge copy", failures)
    check(all(row["base_matches_selected"] for row in rows
              if row["episode"] != "ESeries_055"),
          "base camera override is isolated", failures)
    check(any(not row["base_matches_selected"] for row in rows
              if row["episode"] == "ESeries_055"),
          "shipped base override", failures)
    check(all(sample["runtime"] >= 0 and sample["scene"] >= 0
              for row in rows for sample in row["samples"]),
          "shipped frame lookups", failures)
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
    print("scene_bridge checks: %s" % ("FAIL" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
