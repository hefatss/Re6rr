"""Build a packed car catalog from the shipped specification scripts.

    python tools/engine/car_catalog.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/cars.r6car --report build/tmp/cars.json

Every `data/car/specification/PLC_*_Specification.lua` file defines a
`CarDataList` table. This tool reads the fields the engine needs for car
selection and physics setup and writes fixed-size records consumed by
r6_car_catalog_parse() in the freestanding core. No game data is stored in
this repository.
"""

import argparse
import json
import os
import re
import struct
import sys

MAGIC = b"R6CAR\0\1\0"
VERSION = 1
RECORD_SIZE = 144
HEADER_SIZE = 24

MODEL_SIZE = 24
NAME_SIZE = 64
MAKER_SIZE = 24

NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


def matching_brace(text, opening):
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced CarDataList table")


def decode_string(raw):
    return re.sub(r"\\(.)", r"\1", raw)


def scalar(body, key):
    match = re.search(r'\b' + re.escape(key) + r"\s*=\s*", body)
    if not match:
        return None
    value = body[match.end():]
    string = STRING.match(value)
    if string:
        return decode_string(string.group(1))
    number = NUMBER.match(value)
    if number:
        text = number.group(0)
        return float(text) if any(c in text for c in ".eE") else int(text)
    return None


def as_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    match = NUMBER.search(str(value))
    return int(float(match.group(0))) if match else default


def as_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    match = NUMBER.search(str(value))
    return float(match.group(0)) if match else default


def decode_text(raw):
    for encoding in ("utf-8", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def specification(dump, path):
    text = decode_text(open(path, "rb").read())
    start = text.find("CarDataList")
    if start < 0:
        return None
    brace = text.find("{", start)
    if brace < 0:
        return None
    body = text[brace + 1:matching_brace(text, brace)]
    model = os.path.basename(path).replace("_Specification.lua", "")
    name_jp = "%s %s" % (scalar(body, "CarDataNameJP_1") or "",
                         scalar(body, "CarDataNameJP_2") or "")
    name_us = "%s %s" % (scalar(body, "CarDataNameUS_1") or "",
                         scalar(body, "CarDataNameUS_2") or "")
    entry = {
        "model": model,
        "name": name_us.strip() or name_jp.strip() or
                (scalar(body, "CarNameForPG") or model),
        "name_jp": name_jp.strip(),
        "maker": scalar(body, "CarMakerName") or "",
        "car_name": scalar(body, "CarNameForPG") or "",
        "maker_id": as_int(scalar(body, "MakerID")),
        "model_id": as_int(scalar(body, "ModelID")),
        "visual_model_id": as_int(scalar(body, "VisualModelID")),
        "horsepower": as_int(scalar(body, "Horsepower1st")),
        "engine_cc": as_int(scalar(body, "EngineDisplacement")),
        "drive": as_int(scalar(body, "DriveSystem")),
        "mission": as_int(scalar(body, "MissionNumber")),
        "tire_front": as_float(scalar(body, "TireOutsideFront")),
        "tire_rear": as_float(scalar(body, "TireOutsideRear")),
        "tire_width_front": as_int(scalar(body, "PureTireWidthFront")),
        "tire_width_rear": as_int(scalar(body, "PureTireWidthRear")),
        "glade": scalar(body, "Glade") or "",
        "year": scalar(body, "AnnualSystem") or "",
        "supercharger": as_int(scalar(body, "ExistSupercharger")),
        "dress_up": as_int(scalar(body, "HaveDressUp")),
        "custom_color": as_int(scalar(body, "HaveCustomColor")),
    }
    entry["flags"] = ((entry["dress_up"] & 1) |
                      (entry["custom_color"] & 1) << 1 |
                      (entry["supercharger"] & 1) << 2)
    return entry


def catalog(dump):
    root = os.path.join(dump, "data", "car", "specification")
    result = []
    for name in sorted(os.listdir(root)):
        if not name.startswith("PLC_") or not name.endswith(".lua"):
            continue
        entry = specification(dump, os.path.join(root, name))
        if entry:
            result.append(entry)
    return result


def character_cars(dump):
    root = os.path.join(dump, "data", "car", "car_data", "charCar")
    if not os.path.isdir(root):
        return []
    return sorted(name for name in os.listdir(root)
                  if name.startswith("CRC_") and
                  os.path.isdir(os.path.join(root, name)))


def text_field(value, size, encoding="cp932"):
    raw = (value or "").encode(encoding, "replace")[:size - 1]
    return raw + b"\0" * (size - len(raw))


def pack(entries):
    blob = bytearray(MAGIC)
    blob += struct.pack("<IIII", VERSION, len(entries), RECORD_SIZE, 0)
    for entry in entries:
        blob += text_field(entry["model"], MODEL_SIZE)
        blob += text_field(entry["name"], NAME_SIZE)
        blob += text_field(entry["maker"], MAKER_SIZE)
        blob += struct.pack(
            "<HHHHBBBB", entry["model_id"], entry["visual_model_id"],
            entry["horsepower"], entry["engine_cc"], entry["drive"],
            entry["mission"], entry["flags"], entry["maker_id"] & 0xff)
        blob += struct.pack("<ffff", entry["tire_front"], entry["tire_rear"],
                            float(entry["tire_width_front"]),
                            float(entry["tire_width_rear"]))
        blob += struct.pack("<I", entry["maker_id"])
    if len(blob) != HEADER_SIZE + RECORD_SIZE * len(entries):
        raise ValueError("record layout does not match RECORD_SIZE")
    return bytes(blob)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", help="write packed .r6car catalog")
    parser.add_argument("--report", help="write JSON summary")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    entries = catalog(args.dump)
    if not entries:
        print("no PLC_*_Specification.lua files found")
        return 1
    blob = pack(entries)
    if args.list:
        for index, entry in enumerate(entries):
            print("%3d %-14s %-28s %4d hp %5d cc drive=%d mt=%d" %
                  (index, entry["model"], entry["name"], entry["horsepower"],
                   entry["engine_cc"], entry["drive"], entry["mission"]))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)),
                    exist_ok=True)
        open(args.out, "wb").write(blob)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({
                "records": len(entries),
                "bytes": len(blob),
                "record_size": RECORD_SIZE,
                "characters": character_cars(args.dump),
                "cars": entries,
            }, stream, indent=2, ensure_ascii=False)
    makers = {}
    for entry in entries:
        makers[entry["maker"]] = makers.get(entry["maker"], 0) + 1
    print("cars: %d, %d bytes, %d makers, %d character cars" %
          (len(entries), len(blob), len(makers),
           len(character_cars(args.dump))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
