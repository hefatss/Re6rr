"""Checks for native-interpreted .EES camera and car record fields."""

import argparse
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import ees_scene  # noqa: E402


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def load(dump, name):
    path = os.path.join(dump, ees_scene.SCENE_DIR, *name.split("/"))
    with open(path, "rb") as stream:
        raw = stream.read()
    return raw, ees_scene.parse_ees(raw)


def run(dump, failures):
    raw, header = load(dump, "ESeries_002/FrontEvent/CamData.EES")
    rows = ees_fields.camera_rows(raw, header)
    check(len(rows) == 255, "camera record count", failures)
    check(all(row["type"] in (-1, 1, 2) for row in rows),
          "camera type domain", failures)
    check(all(0 <= row["exact"] <= 1 for row in rows),
          "camera exact flag domain", failures)

    active = [row for row in rows if row["type"] in (1, 2)]
    check(len(active) > 0, "active camera records", failures)
    check(all(row["exact"] == 0 for row in active),
          "active records use inclusive ranges", failures)
    sentinel = [row for row in rows if row["type"] == -1]
    check(all(row["start"] == -1 and row["exact"] == 1
              for row in sentinel), "camera sentinel shape", failures)

    record = active[0]
    start, end = record["start"], record["end"]
    check(record["duration"] > 0 and end >= start,
          "camera duration", failures)
    check(ees_fields.camera_at_frame(rows, start) >= 0,
          "camera lookup at start", failures)
    check(ees_fields.camera_at_frame(rows, end) >= 0,
          "camera lookup at end", failures)
    check(ees_fields.camera_at_frame(rows, start - 1) != 0
          if start > 0 else True, "camera lookup before start", failures)

    camera_offset = header["arrays"][1]["offset"]
    fields = ees_fields.camera_fields(raw, camera_offset)
    check(len(fields) == 31, "named camera field count", failures)
    check(fields["m_CamType"] == 2 and fields["m_StratFrame"] == start,
          "named camera identity", failures)
    check(fields["m_ActFrame"] == record["duration"] and
          fields["m_WiatMode"] == record["exact"],
          "named camera timing", failures)
    # FUN_1401e0330 prints this f32 with "%d"; the raw value is 48.0.
    check(abs(fields["m_StratFieldAngle"] - 48.0) < 0.001,
          "named field angle is f32", failures)
    check(abs(fields["m_LookAtStartRenge"] - 36.0) < 0.001 and
          abs(fields["m_LookAtEndRenge"] - 43.0) < 0.001,
          "named look-at ranges", failures)
    check(abs(fields["m_LookAtStartCamRotY"] - 0.326) < 0.01,
          "named look-at rotation", failures)
    empty = ees_fields.camera_fields(raw, camera_offset + 4 * 0x160)
    check(empty["m_CamType"] == -1 and empty["m_WiatMode"] == 1 and
          empty["m_LookAtStartRenge"] == 0.0,
          "named sentinel fields", failures)

    raw, header = load(dump, "ESeries_001/FrontEvent/CarData0.EES")
    cars = ees_fields.car_rows(raw, header)
    check(len(cars) == 10800, "car record count", failures)
    check(all(len(row["matrix"]) == 16 for row in cars),
          "car matrix width", failures)
    ids = {}
    for row in cars:
        ids[row["car_id"]] = ids.get(row["car_id"], 0) + 1
    check(0 in ids and len(ids) > 1, "shipped car ids", failures)
    check(all(0 <= car_id <= 253 for car_id in ids),
          "car id domain", failures)
    sample = next(row for row in cars if row["car_id"] > 0)
    expected = int(sample["yaw"] * 65536.0 / (2.0 * math.pi) + 0.5) \
        if math.isfinite(sample["yaw"]) else 0
    check(sample["yaw_units"] == expected, "yaw quantisation", failures)

    info = header["arrays"][2]
    first, = struct.unpack_from("<i", raw, info["offset"])
    check(first in (-1, 0), "car_info sentinel domain", failures)
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
    print("ees_fields checks: %s" % ("FAIL" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
