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
  for flag 1. `FUN_1401ca060` accepts types 0 and 2 only. `FUN_1401e0330`
  names 31 further fields from +0x00 to +0x10c; `camera_fields` decodes them.

  car_disp, stride 0x180, array pointer at container +0x1b0
    +0x00 int32  car/actor id (-1 is the native default from FUN_1401cc9d0)
    +0x04 uint8  flags
    +0x10 16 x f32 transform matrix (identity default at stride 0x14)
    +0x150 float yaw in radians, quantised by FUN_1401cba00 as
                round(value * 65536 / 2pi) into an int16 slot

  car_info, stride 0x8c: +0x00 int32, native default -1.

  car_effect, stride 0xa0: FUN_1401cc390 copies 38 dwords and 2 bytes into
  the runtime SInfoCarEffectCopy record at offsets 0x08..0xa0 and 0xdc.
  `car_effect_copy` models the exact source -> destination map.
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
CAR_EFFECT_STRIDE = 0xA0
CAMERA_TYPES = (0, 1, 2)
CAMERA_EMPTY = -1

# FUN_1401cc390: (source byte offset, destination byte offset, width).
# The first 15 dwords and the 4x4 grid are regular; the 7 trailing dwords and
# the two bytes are explicit. Destination layout is SInfoCarEffectCopy.
CAR_EFFECT_COPY = [(index * 4, 8 + index * 4, 4) for index in range(0x0F)]
CAR_EFFECT_COPY += [(0x3C, 0x44, 1)]
for _column in range(4):
    for _row in range(4):
        CAR_EFFECT_COPY.append((0x40 + _column * 4 + _row * 0x10,
                                0x48 + _column * 4 + _row * 0x10, 4))
CAR_EFFECT_COPY += [(0x80 + index * 4, 0x88 + index * 4, 4)
                    for index in range(7)]
CAR_EFFECT_COPY += [(0x9C, 0xDC, 1)]

# FUN_1401e0330 debug logger field names -> (byte offset, kind). The logger
# prints several f32 fields with "%d"; those entries are marked f32 here.
CAMERA_FIELDS = {
    "m_CamType": (0x00, "i32"),
    "m_StratFrame": (0x04, "i32"),
    "m_ActFrame": (0x08, "f32"),
    "m_WiatMode": (0x0C, "u8"),
    "m_StratFieldAngle": (0x90, "f32"),
    "m_EndFieldAngle": (0x94, "f32"),
    "m_FieldAngleCalcId": (0x98, "i32"),
    "m_GlobalLookAt": (0xA8, "i32"),
    "m_LookAtId": (0xB4, "i32"),
    "m_LookAtStartRenge": (0xB8, "f32"),
    "m_LookAtStartCamRotX": (0xBC, "f32"),
    "m_LookAtStartCamRotY": (0xC0, "f32"),
    "m_LookAtStartCamRotZ": (0xC4, "f32"),
    "m_LookAtEndRenge": (0xC8, "f32"),
    "m_LookAtEndCamRotX": (0xCC, "f32"),
    "m_LookAtEndCamRotY": (0xD0, "f32"),
    "m_LookAtEndCamRotZ": (0xD4, "f32"),
    "m_TransCalcId": (0xD8, "i32"),
    "m_RotCalcId": (0xDC, "i32"),
    "m_StratOpRotZ": (0xE0, "f32"),
    "m_EndOpRotZ": (0xE4, "f32"),
    "m_OpRotZCalcId": (0xE8, "i32"),
    "m_LookAtStartOfsetPosX": (0xEC, "f32"),
    "m_LookAtStartOfsetPosY": (0xF0, "f32"),
    "m_LookAtStartOfsetPosZ": (0xF4, "f32"),
    "m_LookAtEndOfsetPosX": (0xF8, "f32"),
    "m_LookAtEndOfsetPosY": (0xFC, "f32"),
    "m_LookAtEndOfsetPosZ": (0x100, "f32"),
    "m_OfsetCalcId": (0x104, "i32"),
    "m_StartConnection": (0x108, "i32"),
    "m_EndConnection": (0x10C, "i32"),
}


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


def camera_fields(raw, offset):
    """Decode the 0x160 record fields named by FUN_1401e0330."""
    record = raw[offset:offset + CAMERA_STRIDE]
    if len(record) < CAMERA_STRIDE:
        raise ValueError("short camera_data record")
    fields = {}
    for name, (field_offset, kind) in CAMERA_FIELDS.items():
        if kind == "u8":
            fields[name] = record[field_offset]
        else:
            fmt = "i" if kind == "i32" else "f"
            fields[name] = struct.unpack_from("<" + fmt, record,
                                              field_offset)[0]
    return fields


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


def car_effect_copy(raw, offset):
    """Model FUN_1401cc390: map a 0xa0 EES record into runtime fields."""
    record = raw[offset:offset + CAR_EFFECT_STRIDE]
    if len(record) < CAR_EFFECT_STRIDE:
        raise ValueError("short car_effect record")
    fields = {}
    for source, destination, width in CAR_EFFECT_COPY:
        fmt = "B" if width == 1 else "I"
        fields[destination] = struct.unpack_from("<" + fmt, record, source)[0]
    return fields


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
