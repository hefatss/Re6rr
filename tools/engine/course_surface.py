"""Recover drivable surface and road width from shipped stage model data.

    python tools/engine/course_surface.py --dump D:\\Games\\W6W-05 --area FUKUOKA

Stage `LOADLIST_*.lua` files pair `ROAD_ADDR` offsets with `ROAD_NAME` strings
inside gzip-compressed `model/bin/*_SECT<id>.bin` containers. Each address points
to an NDWD stream. Course streams use 28-byte vertices:

    +0x00 f32 y, +0x04 f32 z, +0x08 f32 u, +0x0c f32 v,
    +0x10 u32 color, +0x14 u32 normal, +0x18 f32 x

Coordinates use the same source units as `data/course/path/*.bin` (10 units per
metre). Vertices are projected onto the route polyline; the lateral histogram
of road-surface vertices gives half-width and the vertex majority gives a
surface class. No geometry is copied into this repository.
"""

import collections
import gzip
import math
import os
import re
import struct

SECTION_SIZE = 28
SECTION_START = 0x50
SOURCE_UNITS_PER_M = 10.0

SURFACE_ROAD = 0
SURFACE_GRASS = 1
SURFACE_GRAVEL = 2

WINDOW = 5           # path samples per measurement window
CELL = 20.0          # spatial hash cell, metres

ROAD_PREFIX = re.compile(r"(?:broad|nroad|route|road|conc|asph|pavement|"
                         r"futa|tunnel)", re.I)
GRAVEL_PREFIX = re.compile(r"gravel|grail|dirt|sand", re.I)
GRASS_PREFIX = re.compile(r"grass|kusa|green|bush|weed", re.I)


def u32(data, at):
    return struct.unpack_from("<I", data, at)[0]


def f32(data, at):
    return struct.unpack_from("<f", data, at)[0]


def plausible(x, y, z):
    return (math.isfinite(x) and math.isfinite(y) and math.isfinite(z) and
            abs(x) < 200000.0 and abs(z) < 200000.0 and abs(y) < 20000.0)


def loadlist_files(dump, area):
    root = os.path.join(dump, "data", "course", "stage")
    result = []
    for directory, _subdirs, files in os.walk(root):
        parts = directory.replace("\\", "/").split("/")
        stage = next((p for p in parts if p.startswith("A_" + area + "_")),
                     None)
        if not stage or "EXT" in stage or "COMMON" in parts:
            continue
        for name in files:
            if name.startswith("LOADLIST_") and name.endswith(".lua"):
                result.append(os.path.join(directory, name))
    return sorted(result)


def parse_loadlist(path):
    """Return [(section_id, bin_path, [(offset, size, name), ...]), ...]."""
    text = open(path, "rb").read().decode("cp932", "replace")
    blocks = re.split(r"SECTION_ID\s*=\s*(\d+)", text)
    result = []
    for i in range(1, len(blocks) - 1, 2):
        section = int(blocks[i])
        body = blocks[i + 1]
        match = re.search(r'BIN\s*=\s*"sim:([^"]+)"', body)
        if not match:
            continue
        source = match.group(1).replace("/", os.sep)
        binpath = os.path.join(os.path.dirname(path), "bin",
                               os.path.basename(source))
        addr = re.search(r"ROAD_ADDR\s*=\s*\{(.*?)\}", body, re.S)
        names = re.search(r"ROAD_NAME\s*=\s*\{(.*?)\}", body, re.S)
        if not addr or not names:
            continue
        offsets = [int(value, 0) for value in
                   re.findall(r"-?\d+", addr.group(1))]
        labels = re.findall(r'"([^"]+)"', names.group(1))
        streams = []
        for j, label in enumerate(labels):
            if 2 * j + 1 >= len(offsets):
                break
            streams.append((offsets[2 * j], offsets[2 * j + 1], label))
        result.append((section, binpath, streams))
    return result


def classify(name):
    suffix = name.split("PICE_")[-1] if "PICE_" in name else name
    if GRAVEL_PREFIX.search(suffix):
        return SURFACE_GRAVEL
    if GRASS_PREFIX.search(suffix):
        return SURFACE_GRASS
    if ROAD_PREFIX.search(suffix):
        return SURFACE_ROAD
    return -1


def ndwd_vertices(data, offset, size):
    if offset < 0 or size < SECTION_START or offset + size > len(data):
        return []
    record = data[offset:offset + size]
    if record[:4] != b"NDWD":
        return []
    sizes = struct.unpack_from("<4I", record, 0x10)
    start = SECTION_START + sizes[0] + sizes[1]
    end = start + sizes[2]
    if end > len(record):
        return []
    points = []
    for at in range(start, end - SECTION_SIZE + 1, SECTION_SIZE):
        x = f32(record, at + 0x18)
        y = f32(record, at + 0x00)
        z = f32(record, at + 0x04)
        if plausible(x, y, z):
            points.append((x / SOURCE_UNITS_PER_M, z / SOURCE_UNITS_PER_M))
    return points


class PathIndex:
    """Project stream vertices onto a polyline without a slow full scan."""

    def __init__(self, points):
        self.points = points
        self.cells = collections.defaultdict(list)
        for i in range(len(points) - 1):
            x0, z0 = points[i][0], points[i][1]
            x1, z1 = points[i + 1][0], points[i + 1][1]
            lo_x = int(math.floor(min(x0, x1) / CELL))
            hi_x = int(math.floor(max(x0, x1) / CELL))
            lo_z = int(math.floor(min(z0, z1) / CELL))
            hi_z = int(math.floor(max(z0, z1) / CELL))
            for cx in range(lo_x, hi_x + 1):
                for cz in range(lo_z, hi_z + 1):
                    self.cells[(cx, cz)].append(i)

    def project(self, x, z):
        cx = int(math.floor(x / CELL))
        cz = int(math.floor(z / CELL))
        best = None
        best_distance = 1e30
        for index in self.cells.get((cx, cz), ()):
            ax, az = self.points[index][0], self.points[index][1]
            bx, bz = self.points[index + 1][0], self.points[index + 1][1]
            dx, dz = bx - ax, bz - az
            length2 = dx * dx + dz * dz
            if length2 <= 1e-9:
                continue
            t = ((x - ax) * dx + (z - az) * dz) / length2
            t = max(0.0, min(1.0, t))
            px, pz = ax + t * dx, az + t * dz
            distance = (x - px) ** 2 + (z - pz) ** 2
            if distance < best_distance:
                best_distance = distance
                best = (index, math.sqrt(distance))
        if best is None:
            return None
        return best


def measure(dump, area, samples, sections, default_width):
    """Return (widths, surfaces) arrays aligned with `samples`.

    `samples` is the list of dicts built by course_descriptor.build(); each has
    x, y, z and section. The section value selects which stage model bins to
    read, matching the loader's area/stage/section loop in wmn6r.exe.
    """
    wanted = set(sections) - {0}
    records = []
    for path in loadlist_files(dump, area):
        records.extend(parse_loadlist(path))
    if not records:
        return ([default_width] * len(samples),
                [SURFACE_ROAD] * len(samples))

    points = [(s["x"], s["z"]) for s in samples]
    index = PathIndex(points)
    counts = collections.defaultdict(collections.Counter)
    lateral = collections.defaultdict(collections.Counter)
    cache = {}
    for section, binpath, streams in records:
        if section not in wanted or not os.path.isfile(binpath):
            continue
        if binpath not in cache:
            try:
                cache[binpath] = gzip.decompress(open(binpath, "rb").read())
            except (OSError, EOFError):
                cache[binpath] = b""
        blob = cache[binpath]
        if not blob:
            continue
        for offset, size, name in streams:
            surface = classify(name)
            if surface < 0:
                continue
            for x, z in ndwd_vertices(blob, offset, size):
                hit = index.project(x, z)
                if not hit or hit[1] > 30.0:
                    continue
                window = hit[0] // WINDOW
                counts[window][surface] += 1
                if surface == SURFACE_ROAD:
                    lateral[window][int(round(hit[1] * 2.0))] += 1

    widths = []
    surfaces = []
    for i, sample in enumerate(samples):
        window = i // WINDOW
        tally = counts.get(window)
        if tally:
            surfaces.append(tally.most_common(1)[0][0])
        else:
            surfaces.append(SURFACE_ROAD)
        bins = lateral.get(window)
        if bins:
            # Road-edge vertices cluster at the strip boundary; medians,
            # sidewalks and other lanes appear as weaker, wider peaks. Pick
            # the dominant bin inside 1..10 m instead of a high percentile.
            edges = [(value, count) for value, count in bins.items()
                     if 2 <= value <= 20]
            if edges:
                value = sorted(edges, key=lambda item: (-item[1],
                                                        item[0]))[0][0]
                width = max(2.0, min(10.0, value / 2.0))
            else:
                width = default_width
        else:
            width = default_width
        widths.append(width)
    return widths, surfaces


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    ap.add_argument("--area", default="FUKUOKA")
    ap.add_argument("--section", type=int, default=101)
    args = ap.parse_args()

    records = []
    for path in loadlist_files(args.dump, args.area):
        records.extend(parse_loadlist(path))
    print("%s: %d LOADLIST records, %d ROAD streams" %
          (args.area, len(records),
           sum(len(streams) for _s, _b, streams in records)))
    for section, binpath, streams in records:
        if section != args.section:
            continue
        tally = collections.Counter(classify(name) for _o, _s, name in streams)
        print("  section %d: %s, classes %s" %
              (section, os.path.basename(binpath), dict(tally)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
