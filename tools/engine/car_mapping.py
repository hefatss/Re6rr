"""Infer character-car → player-model pairs from shipped position scripts.

The dump has no CRC_* → PLC_* table: each `getTirePos_<car>.lua` only contains
its own name. This tool combines the name prefix before the first underscore
with the four tire positions:

    CRC_928GT_Masaki -> PLC_928GT    (exact prefix)
    CRC_964_Shima    -> PLC_964T36   (prefix + nearest tire layout)
    CRC_R964_Kijima  -> PLC_R964     (exact prefix, race-body tires differ)
    CRC_AP2_Yuji1st  -> PLC_AP2      (exact prefix)

`CRC_DUMMY*` and non-car props (bus, truck) stay unmapped: their tire layout
matches a road car by accident, but the name gives no usable model prefix.

    python tools/engine/car_mapping.py --dump D:\\Games\\W6W-05 --report out.json

Results are derived, not shipped facts; every entry records its method and
the RMS tire-position distance in source decimetres.
"""

import argparse
import json
import math
import os
import re

POS = os.path.join("data", "car", "position", "pos")
CHAR = os.path.join("data", "car", "car_data", "charCar")
NAME = re.compile(r"getTirePos_(CRC|PLC)_(.+)\.lua$")
NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)")
MAX_DISTANCE = 0.6


def decode(path):
    raw = open(path, "rb").read()
    for encoding in ("utf-8", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def tires(text):
    start = text.find("TirePos")
    if start < 0:
        return None
    block = text[start:start + 1600]
    match = re.search(r"TirePos\s*=\s*\{(.*?)\}\s*,\s*\n\s*\w+\s*=",
                      block, re.S)
    if not match:
        return None
    values = [float(value) for value in NUMBER.findall(match.group(1))]
    return values[:12] if len(values) >= 12 else None


def inventory(dump):
    root = os.path.join(dump, POS)
    result = {"CRC": {}, "PLC": {}}
    for name in os.listdir(root):
        match = NAME.match(name)
        if not match:
            continue
        values = tires(decode(os.path.join(root, name)))
        if values:
            result[match.group(1)][match.group(2)] = values
    return result


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def base_name(name):
    return name.split("_", 1)[0].upper()


def candidates_for(base, plc):
    keys = {base}
    if len(base) > 1 and base.startswith("R"):
        keys.add(base[1:])
    return [model for model in sorted(plc) if any(
        model.upper() == key or model.upper().startswith(key) or
        key.startswith(model.upper()) for key in keys)]


def map_characters(dump):
    found = inventory(dump)
    crc, plc = found["CRC"], found["PLC"]
    result = []
    for car in sorted(crc):
        base = base_name(car)
        candidates = candidates_for(base, plc)
        ranked = sorted((distance(crc[car], plc[model]), model)
                        for model in (candidates or plc))
        nearest = ranked[0] if ranked else (float("inf"), "")
        exact = [model for model in candidates if model.upper() == base or
                 base.startswith(model.upper())]
        if "DUMMY" in car.upper():
            model = None
        elif exact:
            model = exact[0]
        elif nearest[0] <= MAX_DISTANCE:
            model = nearest[1]
        else:
            model = None
        result.append({
            "car": "CRC_" + car,
            "model": "PLC_" + model if model else None,
            "method": ("prefix" if model in candidates
                       else "tire-nearest" if model else "unmapped"),
            "distance": round(nearest[0], 4),
            "candidates": ["PLC_" + item for item in candidates],
        })
    return result


def character_dirs(dump):
    root = os.path.join(dump, CHAR)
    if not os.path.isdir(root):
        return []
    return sorted(name for name in os.listdir(root)
                  if name.startswith("CRC_") and
                  os.path.isdir(os.path.join(root, name)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--report", help="write JSON mapping")
    args = parser.parse_args()

    rows = map_characters(args.dump)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({
                "characters": rows,
                "missing_scripts": sorted(
                    set(character_dirs(args.dump)) -
                    {row["car"] for row in rows}),
            }, stream, indent=2, ensure_ascii=False)
    mapped = sum(1 for row in rows if row["model"])
    print("character cars: %d, mapped %d, prefix %d, nearest %d, dirs %d" %
          (len(rows), mapped,
           sum(1 for row in rows if row["method"] == "prefix"),
           sum(1 for row in rows if row["method"] == "tire-nearest"),
           len(character_dirs(args.dump))))
    for row in rows[:8]:
        print("  %-28s -> %-14s %-12s %.3f" %
              (row["car"], row["model"] or "-", row["method"],
               row["distance"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
