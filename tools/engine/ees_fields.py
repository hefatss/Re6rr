"""Interpret `.EES` record fields using shipped native consumers.

    python tools/engine/ees_fields.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/ees_fields.json

Proven from `wmn6r.exe` (VA, image base 0x140000000):

  camera_data, stride 0x160, array pointer at container +0x1a8
    +0x00 int32  camera type (1/2 used, -1 is the empty sentinel)
    +0x04 int32  start frame
    +0x08 float  duration in frames (end = start + duration)
    +0x0c uint8  exact-frame flag: 1 = match only start, 0 = inclusive range
  `FUN_1401c8f60` converts start to f32, adds duration, truncates to int and
  compares against the frame: start <= frame <= end for flag 0, start == frame
  for flag 1. `FUN_1401ca060` accepts types 0 and 2 only.

  car_disp, stride 0x180, array pointer at container +0x1b0
    +0x00 int32  car/actor id (-1 is the native default from FUN_1401cc9d0)
    +0x04 uint8  flags
    +0x10 16 x f32 transform matrix (identity default at stride 0x14)
    +0x150 float yaw in radians, quantised by FUN_1401cba00 as
                round(value * 65536 / 2pi) into an int16 slot

  car_info, stride 0x8c: +0x00 int32, native default -1.
"""

import argparse
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ees_scene  # noqa: E402

CAMERA_STRIDE = 0x160
CAR_DISP_STRIDE = 0x180
CAR_INFO_STRIDE = 0x8C
CAMERA_TYPES = (0, 1, 2)
CAMERA_EMPTY = -1


def camera_record(raw, offset):
    record = raw[offset:offset + CAMERA_STRIDE]
    if len(record) < CAMERA_STRIDE:
        raise ValueError("short camera_data record")
    kind, start = struct.unpack_from("<ii", record, 0)
    duration, = struct.unpack_from("<f", record, 8)
    return {
        "type": kind, "start": start, "duration": duration,
        "exact": record[0x0C],
        "end": int(start + duration) if math.isfinite(duration) else None,
    }


def camera_at_frame(records, frame):
    """0x1401c8f60: last record matching `frame`; -1 for no match."""
    found = -1
    for index, record in enumerate(records):
        if record["type"] == CAMERA_EMPTY:
            continue
        start = record["start"]
        end = record["end"]
        if record["exact"] == 1:
            if start == frame:
                found = index
        elif end is not None and start <= frame <= end:
            found = index
    return found


def car_disp_record(raw, offset):
    record = raw[offset:offset + CAR_DISP_STRIDE]
    if len(record) < CAR_DISP_STRIDE:
        raise ValueError("short car_disp record")
    car_id, = struct.unpack_from("<i", record, 0)
    yaw, = struct.unpack_from("<f", record, 0x150)
    matrix = struct.unpack_from("<16f", record, 0x10)
    return {
        "car_id": car_id,
        "flags": record[4],
        "matrix": matrix,
        "yaw": yaw,
        "yaw_units": int(yaw * 65536.0 / (2.0 * math.pi) + 0.5)
        if math.isfinite(yaw) else 0,
    }


def camera_rows(raw, header):
    array = header["arrays"][1]
    return [camera_record(raw, array["offset"] + index * CAMERA_STRIDE)
            for index in range(header["count"])]


def car_rows(raw, header):
    array = header["arrays"][0]
    return [car_disp_record(raw, array["offset"] + index * CAR_DISP_STRIDE)
            for index in range(header["count"])]


def build(dump):
    root = os.path.join(dump, ees_scene.SCENE_DIR)
    result = {"camera": {}, "car": {}}
    for directory, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".EES"):
                continue
            path = os.path.join(directory, name)
            with open(path, "rb") as stream:
                raw = stream.read()
            key = os.path.relpath(path, root).replace("\\", "/")
            header = ees_scene.parse_ees(raw)
            if header["kind"] == "cam":
                rows = camera_rows(raw, header)
                result["camera"][key] = {
                    "count": len(rows),
                    "sentinel": sum(1 for row in rows
                                    if row["type"] == CAMERA_EMPTY),
                    "active": sum(1 for row in rows
                                  if row["type"] in (1, 2)),
                    "types": sorted(set(row["type"] for row in rows)),
                    "first_match": camera_at_frame(rows, 1),
                }
            else:
                rows = car_rows(raw, header)
                ids = {}
                for row in rows:
                    ids[row["car_id"]] = ids.get(row["car_id"], 0) + 1
                result["car"][key] = {
                    "count": len(rows),
                    "car_ids": ids,
                }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", help="write JSON report")
    args = parser.parse_args()

    sections = build(args.dump)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf8") as stream:
            json.dump(sections, stream, indent=2, sort_keys=True)
    cameras = sections["camera"]
    cars = sections["car"]
    print("camera files %d, active records %d, sentinel records %d" %
          (len(cameras), sum(row["active"] for row in cameras.values()),
           sum(row["sentinel"] for row in cameras.values())))
    print("car files %d, records %d" %
          (len(cars), sum(row["count"] for row in cars.values())))
    for key in sorted(cameras)[:3]:
        print("  %-45s %s" % (key, cameras[key]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
