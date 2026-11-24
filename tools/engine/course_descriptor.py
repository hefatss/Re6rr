"""Build an r6course descriptor from the shipped course path data.

    python tools/engine/course_descriptor.py --dump D:\\Games\\W6W-05 \
        --route FUKUOKA --out build/tmp/fukuoka.r6course

The route order and loop flag come from data/course/debug/course_viewer_multi_path.lua.
Each path bin is a headerless sequence of float32 (x,y,z) triples in source
world units; NavimapParam.lua says 1 m = 10 units, so positions are divided by
10. Section polygons in data/course/section/SECT_A_<AREA>.lua are used to tag
each sample with a section ID. The packed output is consumed by
r6_course_descriptor_parse() in the freestanding C core.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6CRS\0\1\0"
HEADER_SIZE = 24
VERTEX_SIZE = 20
VERSION = 1

FLAG_CHECKPOINT = 1
FLAG_START = 2
FLAG_GOAL = 4
FLAG_JUNCTION = 8

NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def matching_brace(text, opening):
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced brace")


def routes(dump):
    """Parse PathTable from the course viewer Lua script."""
    script = os.path.join(dump, "data", "course", "debug",
                          "course_viewer_multi_path.lua")
    text = open(script, "rb").read().decode("cp932", "replace")
    table = text[text.index("PathTable"):]
    result = []
    for match in re.finditer(r"PathList\s*=\s*\{(.*?)\}", table, re.S):
        names = re.findall(r'"([^"]+\.bin)"', match.group(1))
        if not names:
            continue
        before = table[:match.start()]
        menu = list(re.finditer(r'MenuText\s*=\s*"([^"]+)"', before))
        area = list(re.finditer(r"AreaId\s*=\s*(\d+)", before))
        loop = list(re.finditer(r"Loop\s*=\s*(\d+)", before))
        direction = list(re.finditer(r"CameraDirection\s*=\s*(\d+)", before))
        if not menu:
            continue
        result.append({
            "name": menu[-1].group(1),
            "area_id": int(area[-1].group(1)) if area else -1,
            "loop": int(loop[-1].group(1)) if loop else 0,
            "camera_direction": int(direction[-1].group(1))
                                if direction else 0,
            "paths": names,
        })
    return result


def path_index(dump):
    root = os.path.join(dump, "data", "course", "path")
    result = {}
    for directory, _subdirs, files in os.walk(root):
        for name in files:
            if name.endswith(".bin"):
                result.setdefault(name, os.path.join(directory, name))
    return result


def read_path(path):
    blob = open(path, "rb").read()
    if len(blob) % 12:
        raise ValueError("%s: size %d is not a multiple of 12" %
                         (path.name if hasattr(path, "name") else path,
                          len(blob)))
    count = len(blob) // 12
    values = struct.unpack("<%df" % (count * 3), blob)
    return [(values[i] / 10.0, values[i + 1] / 10.0, values[i + 2] / 10.0)
            for i in range(0, len(values), 3)]


def section_polygons(path):
    """Return [(section_id, [(x, z), ...]), ...] from a SECT_A_*.lua file."""
    text = open(path, "rb").read().decode("cp932", "replace")
    result = []
    for sect in re.finditer(r"SECT_ID\s*=\s*(\d+)", text):
        geo = re.search(r"GEO\s*=\s*\{", text[sect.end():])
        if not geo:
            continue
        opening = sect.end() + geo.end() - 1
        closing = matching_brace(text, opening)
        body = text[opening + 1:closing]
        for nested in re.finditer(r"\{(.*?)\}", body, re.S):
            values = [float(value) for value in
                      NUMBER.findall(nested.group(1))]
            edges = [values[i:i + 6] for i in range(0, len(values) - 5, 6)]
            polygon = []
            for edge in edges:
                x, _y, z, dx, _dy, dz = edge
                if not polygon:
                    polygon.append((x, z))
                polygon.append((x + dx, z + dz))
            if len(polygon) >= 3:
                result.append((int(sect.group(1)), polygon))
    return result


def inside(polygon, x, z):
    hit = False
    previous = polygon[-1]
    for current in polygon:
        if ((current[1] > z) != (previous[1] > z) and
                x < (previous[0] - current[0]) * (z - current[1]) /
                (previous[1] - current[1]) + current[0]):
            hit = not hit
        previous = current
    return hit


def section_for_point(polygons, x, z, fallback):
    for section_id, polygon in polygons:
        if inside(polygon, x, z):
            return section_id
    return fallback


def section_from_name(name):
    match = re.search(r"Sect(\d+)", name, re.I)
    return 100 + int(match.group(1)) if match else 0


def build(dump, route, max_points, half_width):
    selected = [item for item in routes(dump) if item["name"] == route]
    if not selected:
        raise ValueError("route %r not found" % route)
    selected = selected[0]
    files = path_index(dump)
    polygons = []
    area_files = [name for name in selected["paths"] if name in files]
    if area_files:
        sample_dir = os.path.dirname(files[area_files[0]])
        area_name = os.path.basename(sample_dir)
        section_file = os.path.join(dump, "data", "course", "section",
                                    "SECT_A_%s.lua" % area_name)
        if os.path.isfile(section_file):
            polygons = section_polygons(section_file)

    samples = []
    pieces = []
    for name in selected["paths"]:
        source = files.get(name)
        if not source:
            raise ValueError("path file %r not in dump" % name)
        points = read_path(source)
        if not points:
            continue
        pieces.append({
            "name": name,
            "points": len(points),
            "first": points[0],
            "last": points[-1],
            "section": section_from_name(name),
        })
        for point in points:
            if samples and abs(point[0] - samples[-1]["x"]) < 1e-4 and \
                    abs(point[2] - samples[-1]["z"]) < 1e-4:
                continue
            samples.append({
                "x": point[0], "y": point[1], "z": point[2],
                "section": section_from_name(name),
                "flags": 0,
            })

    if max_points > 0 and len(samples) > max_points:
        step = len(samples) / float(max_points)
        picked = [samples[int(index * step)] for index in range(max_points)]
        samples = picked
    if len(samples) < 2:
        raise ValueError("route has fewer than two samples")

    for sample in samples:
        sample["section"] = section_for_point(
            polygons, sample["x"], sample["z"], sample["section"])

    samples[0]["flags"] |= FLAG_START
    samples[-1]["flags"] |= FLAG_GOAL
    for piece in pieces[1:]:
        target = min(samples, key=lambda s:
                     (s["x"] - piece["first"][0]) ** 2 +
                     (s["z"] - piece["first"][2]) ** 2)
        target["flags"] |= FLAG_CHECKPOINT
        if "jct" in piece["name"].lower() or "junction" in piece["name"].lower():
            target["flags"] |= FLAG_JUNCTION
        if not target["section"]:
            target["section"] = piece["section"]

    blob = bytearray(MAGIC)
    blob += struct.pack("<IIII", VERSION, 1 if selected["loop"] else 0,
                        len(samples), 0)
    for sample in samples:
        blob += struct.pack("<ffff", sample["x"], sample["y"], sample["z"],
                            half_width)
        blob += struct.pack("<BBH", 0, sample["flags"],
                            min(0xffff, sample["section"]))

    header = {
        "route": route,
        "area_id": selected["area_id"],
        "loop": selected["loop"],
        "camera_direction": selected["camera_direction"],
        "source_units_per_m": 10,
        "half_width": half_width,
        "vertices": len(samples),
        "bytes": len(blob),
        "pieces": pieces,
        "sections": sorted({sample["section"] for sample in samples}),
        "flags": {
            "start": sum(1 for s in samples if s["flags"] & FLAG_START),
            "goal": sum(1 for s in samples if s["flags"] & FLAG_GOAL),
            "checkpoint": sum(1 for s in samples
                              if s["flags"] & FLAG_CHECKPOINT),
        },
        "seams": [{
            "piece": piece["name"],
            "gap_m": 0.0,
        } for piece in pieces],
    }
    return bytes(blob), header


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--route", help="MenuText from course_viewer_multi_path.lua")
    parser.add_argument("--list-routes", action="store_true")
    parser.add_argument("--out", help="write packed .r6course descriptor")
    parser.add_argument("--report", help="write JSON summary")
    parser.add_argument("--max-points", type=int, default=0,
                        help="downsample to at most N vertices (0 keeps all)")
    parser.add_argument("--half-width", type=float, default=6.0,
                        help="road half-width in metres; not in the dump")
    args = parser.parse_args()

    all_routes = routes(args.dump)
    if args.list_routes:
        for item in all_routes:
            print("%-24s area=%2d loop=%d paths=%d" %
                  (item["name"], item["area_id"], item["loop"],
                   len(item["paths"])))
        return 0
    if not args.route:
        parser.error("--route or --list-routes is required")

    blob, header = build(args.dump, args.route, args.max_points,
                         args.half_width)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "wb").write(blob)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump(header, stream, indent=2, ensure_ascii=False)
    print("%s: %d vertices, %d bytes, closed=%d, sections %s" %
          (header["route"], header["vertices"], header["bytes"],
           header["loop"], header["sections"][:12]))
    if not args.out:
        print("(no --out given; descriptor not written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
