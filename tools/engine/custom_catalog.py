"""Build a packed customization catalog from the shipped Lua/name tables.

    python tools/engine/custom_catalog.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/custom.r6custom --report build/tmp/custom.json

Sections: global colour library with Japanese message-DB names, SWH_* wheel
IDs, CAR_PARTS_ID_* aero names, per-car palette/wheel/wing data from the
PLC_*_Specification.lua scripts, and the TireDefine.lua scale constants. No
game data is committed; the output is a derived .r6custom blob.
"""

import argparse
import json
import os
import re
import struct

import car_catalog

MAGIC = b"R6CUS\0\1\0"
VERSION = 1
HEADER_SIZE = 32
COLOR_SIZE = 96
WHEEL_SIZE = 48
AERO_SIZE = 64
TUNE_SIZE = 160
TIRE_SIZE = 8

COLOR_LIBRARY = os.path.join("data", "car", "color", "LibraryColor.lua")
MSGDB = os.path.join("data_jp", "msgdb", "msgdb.lua")
TIRE_DEFINE = os.path.join("data", "car", "tire", "script", "TireDefine.lua")
NAME_TABLES = "name_tables.json"
WHEEL_RVA = 0x1c57dd8
PARTS_RVA = 0x1c581e0

NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
AERO_KINDS = (
    ("AERO", 1), ("CUST_WING", 2), ("WING", 2), ("BONNET", 4),
    ("SPOILER", 8), ("DIFFUSER", 16), ("SKIRT", 32), ("WHEEL", 64)
)
AERO_FILTER = re.compile("|".join(name for name, _ in AERO_KINDS))


def read_text(path):
    raw = open(path, "rb").read()
    for encoding in ("utf-8", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", "replace")


def strip_comments(text):
    return re.sub(r"--[^\n]*", "", text)


def matching_brace(text, opening):
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced Lua table")


def table_body(text, key):
    match = re.search(r"\b" + re.escape(key) + r"\s*=\s*\{", text)
    if not match:
        return ""
    opening = text.find("{", match.start())
    return text[opening + 1:matching_brace(text, opening)]


def table_numbers(body):
    return [float(value) if any(ch in value for ch in ".eE")
            else int(value) for value in NUMBER.findall(strip_comments(body))]


def text_field(value, size, encoding="cp932"):
    raw = (value or "").encode(encoding, "replace")[:size - 1]
    return raw + b"\0" * (size - len(raw))


def color_names(dump):
    text = read_text(os.path.join(dump, MSGDB))
    pattern = re.compile(
        r'MessageID\s*=\s*"custom_color_(\d+)"\s*,\s*'
        r'Message\s*=\s*"([^"]*)"')
    return {int(index): message for index, message in pattern.findall(text)}


def color_library(dump):
    text = read_text(os.path.join(dump, COLOR_LIBRARY))
    body = strip_comments(table_body(text, "ColorList"))
    matches = list(re.finditer(r'name\s*=\s*"type(\d+)"', body))
    names = color_names(dump)
    result = []
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        entry = body[match.start():stop]
        vec = table_numbers(table_body(entry, "ListVec4"))
        params = table_numbers(table_body(entry, "ListFloat"))
        ints = table_numbers(table_body(entry, "ListInt"))
        if len(vec) < 12 or len(params) < 4 or len(ints) < 3:
            continue
        identifier = int(match.group(1))
        result.append({
            "id": identifier,
            "name": names.get(identifier - 1, match.group(0)
                              .split('"')[1]),
            "body0": vec[0:4],
            "body1": vec[4:8],
            "spec": vec[8:12],
            "params": params[0:4],
            "icon": int(ints[0]),
            "feel": int(ints[2]),
        })
    declared = car_catalog.scalar(strip_comments(text), "COLOR_MAX")
    if declared and result and len(result) != int(declared):
        raise ValueError("COLOR_MAX %s but %d entries" %
                         (declared, len(result)))
    return result


def name_table(recon, rva):
    tables = json.load(open(os.path.join(recon, NAME_TABLES),
                            encoding="utf8"))["strings"]
    for table in tables:
        if int(table.get("rva", 0)) == rva:
            return list(table["names"])
    raise ValueError("name table 0x%x not found" % rva)


def wheels(recon, dump):
    names = name_table(recon, WHEEL_RVA)
    root = os.path.join(dump, "data", "car", "wheel")
    files = set(os.listdir(root)) if os.path.isdir(root) else set()
    result = []
    for index, name in enumerate(names):
        if not name.startswith("SWH_"):
            continue
        result.append({
            "id": index,
            "name": name,
            "flags": 1 if name + ".mdl" in files else 0,
        })
    return result


def aero_flags(name):
    flags = 0
    for key, bit in AERO_KINDS:
        if key in name:
            flags |= bit
    return flags


def aeros(recon):
    names = name_table(recon, PARTS_RVA)
    return [{"id": index, "name": name, "flags": aero_flags(name)}
            for index, name in enumerate(names) if AERO_FILTER.search(name)]


def tire_scales(dump):
    text = strip_comments(read_text(os.path.join(dump, TIRE_DEFINE)))
    result = []
    for match in re.finditer(r"WHEEL_SCALE_INC_(\d+)\s*=\s*"
                             r"([-+]?[\d.]+)", text):
        result.append({"kind": 0, "index": int(match.group(1)) - 13,
                       "value": float(match.group(2))})
    for match in re.finditer(r"TIRE_WIDTH_SCALE_(\d+)\s*=\s*"
                             r"([-+]?[\d.]+)", text):
        result.append({"kind": 1, "index": int(match.group(1)) - 155,
                       "value": float(match.group(2))})
    diameters = table_numbers(table_body(text, "TIRE_OUTER_DIAMETER"))
    for index, diameter in enumerate(diameters):
        result.append({"kind": 2, "index": index, "value": diameter})
    return sorted(result, key=lambda row: (row["kind"], row["index"]))


def spec_body(path):
    text = read_text(path)
    start = text.find("CarDataList")
    if start < 0:
        return ""
    opening = text.find("{", start)
    return text[opening + 1:matching_brace(text, opening)]


def tunes(dump):
    root = os.path.join(dump, "data", "car", "specification")
    result = []
    cars = car_catalog.catalog(dump)
    for car in cars:
        body = spec_body(os.path.join(root, car["model"] +
                                      "_Specification.lua"))
        get = lambda key: car_catalog.scalar(body, key)
        wing_a = sum(1 << bit for bit, letter in enumerate("ABCDEFGH")
                     if car_catalog.as_int(get("HaveWing" + letter)) == 1)
        wing_n = sum(1 << bit for bit, letter in enumerate("ABCDEFGHIJKLMN")
                     if car_catalog.as_int(get("HaveWingN_" + letter)) == 1)
        defaults = [car_catalog.as_int(get("DefaultColorID_%02d" % i))
                    for i in range(11)]
        customs = [car_catalog.as_int(get("CustomColorID_%02d" % i))
                   for i in range(1, 41)]
        result.append({
            "model": car["model"],
            "aero_category": car_catalog.as_int(get("AeroCategoryID")),
            "limited_parts": car_catalog.as_int(get("LimitedParts")),
            "pure_wheel_front": car_catalog.as_int(get("PureWheelIncFront")),
            "pure_wheel_rear": car_catalog.as_int(get("PureWheelIncRear")),
            "custom_wheel_front": car_catalog.as_int(
                get("CustomWheelIncFront")),
            "custom_wheel_rear": car_catalog.as_int(get("CustomWheelIncRear")),
            "change_tuning_disp": car_catalog.as_int(get("ChangeTuningDisp")),
            "custom_gt_wing": car_catalog.as_int(get("HaveCustomGTWing")),
            "wing_a_h": wing_a,
            "wing_n": wing_n,
            "default_color_count": sum(1 for value in defaults if value),
            "custom_color_count": sum(1 for value in customs if value),
            "default_color_ids": defaults,
            "custom_color_ids": customs,
            "flags": car["flags"],
        })
    return result


def build(dump, recon):
    return {
        "colors": color_library(dump),
        "wheels": wheels(recon, dump),
        "aeros": aeros(recon),
        "tunes": tunes(dump),
        "tires": tire_scales(dump),
    }


def pack(sections):
    colors = sections["colors"]
    wheels = sections["wheels"]
    aeros = sections["aeros"]
    tunes = sections["tunes"]
    tires = sections["tires"]
    blob = bytearray(MAGIC)
    blob += struct.pack("<IIIIII", VERSION, len(colors), len(wheels),
                        len(aeros), len(tunes), len(tires))
    for entry in colors:
        blob += struct.pack("<HHHH", entry["id"], entry["icon"],
                            entry["feel"], 0)
        for key in ("body0", "body1", "spec"):
            blob += struct.pack("<ffff", *entry[key])
        blob += struct.pack("<ffff", *entry["params"])
        blob += text_field(entry["name"], 24)
    for entry in wheels:
        blob += struct.pack("<HH", entry["id"], 0)
        blob += text_field(entry["name"], 24)
        blob += struct.pack("<II", entry["flags"], 0)
        blob += b"\0" * 12
    for entry in aeros:
        blob += struct.pack("<HH", entry["id"], 0)
        blob += text_field(entry["name"], 48)
        blob += struct.pack("<II", entry["flags"], 0)
        blob += b"\0" * 4
    for entry in tunes:
        blob += text_field(entry["model"], 24)
        blob += struct.pack("<HHBBBBBBHHHH",
                            entry["aero_category"], entry["limited_parts"],
                            entry["pure_wheel_front"], entry["pure_wheel_rear"],
                            entry["custom_wheel_front"],
                            entry["custom_wheel_rear"],
                            entry["change_tuning_disp"],
                            entry["custom_gt_wing"], entry["wing_a_h"],
                            entry["wing_n"], entry["default_color_count"],
                            entry["custom_color_count"])
        blob += struct.pack("<11H", *entry["default_color_ids"])
        blob += struct.pack("<40H", *entry["custom_color_ids"])
        blob += struct.pack("<II", entry["flags"], 0)
        blob += b"\0" * 8
    for entry in tires:
        blob += struct.pack("<HHf", entry["kind"], entry["index"],
                            entry["value"])
    expected = (HEADER_SIZE + COLOR_SIZE * len(colors) +
                WHEEL_SIZE * len(wheels) + AERO_SIZE * len(aeros) +
                TUNE_SIZE * len(tunes) + TIRE_SIZE * len(tires))
    if len(blob) != expected:
        raise ValueError("custom catalog layout does not match sizes")
    return bytes(blob)


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--recon", default=os.path.join(root, "docs", "recon"))
    parser.add_argument("--out")
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    sections = build(args.dump, args.recon)
    blob = pack(sections)
    if args.list:
        for index, entry in enumerate(sections["colors"][:10]):
            label = entry["name"].encode("ascii", "replace").decode("ascii")
            print("%3d %-10s body0=(%.3f %.3f %.3f)" %
                  (index, label, *entry["body0"][:3]))
        for entry in sections["wheels"][:5]:
            print("wheel %3d %s" % (entry["id"], entry["name"]))
        for entry in sections["aeros"][:5]:
            print("aero  %3d %s" % (entry["id"], entry["name"]))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)),
                    exist_ok=True)
        open(args.out, "wb").write(blob)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"bytes": len(blob),
                       "sections": {key: len(value)
                                    for key, value in sections.items()},
                       **sections}, stream, indent=2, ensure_ascii=False)
    print("custom: %d colors, %d wheels, %d aero parts, %d tunes, "
          "%d tire scales, %d bytes" %
          (len(sections["colors"]), len(sections["wheels"]),
           len(sections["aeros"]), len(sections["tunes"]),
           len(sections["tires"]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
