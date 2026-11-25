"""Inventory the header and typed arrays of shipped `EventScene2` `.EES` files.

    python tools/engine/ees_scene.py --dump D:\\Games\\W6W-05 --report build/tmp/ees.json --list
    python tools/engine/ees_scene.py --dump D:\\Games\\W6W-05 \
        --extract ESeries_001/FrontEvent/CamData.EES --array 0 --out build/tmp/cam_info.bin

Native evidence: `FUN_1401cd0a0` (camera header) and `FUN_1401cd650` (car
header) in `wmn6r.exe`. Files are raw header + packed record arrays; no
decryption or decompression exists on the load path. No game data is stored in
this repository.
"""

import argparse
import json
import os
import struct

MAGIC_CAM = (0x2712, 0x2713)
MAGIC_CAR = 0x2712
SCENE_DIR = os.path.join("data_jp", "scene")


def u32(raw, offset):
    return struct.unpack_from("<I", raw, offset)[0]


def parse_ees(raw):
    if len(raw) < 0x130:
        raise ValueError("short .EES file")
    version = u32(raw, 0)
    if version in MAGIC_CAM and u32(raw, 0x110) == len(raw):
        count = u32(raw, 0x104)
        header = u32(raw, 0x114)
        info_size = u32(raw, 0x118)
        data_size = u32(raw, 0x11c)
        if header not in (0x1a8, 0x1b0) or info_size != count * 0x50 or \
                data_size != count * 0x160 or \
                header + info_size + data_size != len(raw):
            raise ValueError("inconsistent camera .EES header")
        return {
            "kind": "cam", "version": version, "file_size": len(raw),
            "count": count, "header_size": header,
            "arrays": [
                {"name": "camera_info", "count": count, "stride": 0x50,
                 "offset": header, "size": info_size},
                {"name": "camera_data", "count": count, "stride": 0x160,
                 "offset": header + info_size, "size": data_size},
            ],
        }
    if version == MAGIC_CAR and u32(raw, 0x114) == len(raw):
        count = u32(raw, 0x104)
        effect_count = u32(raw, 0x108)
        header = u32(raw, 0x118)
        disp_size = u32(raw, 0x11c)
        effect_size = u32(raw, 0x120)
        info_size = u32(raw, 0x124)
        if header not in (0x1bc, 0x1c8) or \
                disp_size != count * 0x180 or \
                effect_size != effect_count * 0xa0 or \
                info_size != count * 0x8c or \
                header + disp_size + effect_size + info_size != len(raw):
            raise ValueError("inconsistent car .EES header")
        return {
            "kind": "car", "version": version, "file_size": len(raw),
            "count": count, "effect_count": effect_count,
            "header_size": header,
            "arrays": [
                {"name": "car_disp", "count": count, "stride": 0x180,
                 "offset": header, "size": disp_size},
                {"name": "car_effect", "count": effect_count, "stride": 0xa0,
                 "offset": header + disp_size, "size": effect_size},
                {"name": "car_info", "count": count, "stride": 0x8c,
                 "offset": header + disp_size + effect_size,
                 "size": info_size},
            ],
        }
    raise ValueError("unknown .EES header version 0x%x" % version)


def collect(dump):
    root = os.path.join(dump, SCENE_DIR)
    files = {}
    for directory, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".EES"):
                continue
            path = os.path.join(directory, name)
            with open(path, "rb") as stream:
                raw = stream.read()
            key = os.path.relpath(path, root).replace("\\", "/")
            files[key] = parse_ees(raw)
    return {"files": files}


def extract(dump, name, index, output):
    path = os.path.join(dump, SCENE_DIR, *name.split("/"))
    with open(path, "rb") as stream:
        raw = stream.read()
    header = parse_ees(raw)
    if index < 0 or index >= len(header["arrays"]):
        raise ValueError("array %d outside %s" % (index, name))
    array = header["arrays"][index]
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "wb") as stream:
        stream.write(raw[array["offset"]:array["offset"] + array["size"]])
    return header, array


def report_text(data):
    files = data["files"]
    kinds = {}
    versions = {}
    arrays = {}
    for item in files.values():
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
        versions[hex(item["version"])] = versions.get(hex(item["version"]), 0) + 1
        for array in item["arrays"]:
            arrays[array["name"]] = arrays.get(array["name"], 0) + 1
    return "\n".join([
        "%d .EES files: %s, versions %s" %
        (len(files), ", ".join("%s=%d" % item
                               for item in sorted(kinds.items())),
         ", ".join("%s=%d" % item for item in sorted(versions.items()))),
        "arrays: %s" % ", ".join("%s=%d" % item
                                 for item in sorted(arrays.items())),
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--extract")
    parser.add_argument("--array", type=int, default=0)
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.extract:
        header, array = extract(args.dump, args.extract, args.array,
                                args.out or os.path.join("build", "tmp",
                                                         "ees_array.bin"))
        print("extracted %s[%d] %s: %d records x 0x%x = %d bytes" %
              (args.extract, args.array, array["name"], array["count"],
               array["stride"], array["size"]))
        return 0

    data = collect(args.dump)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
    print(report_text(data) if args.list else
          report_text(data).splitlines()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
