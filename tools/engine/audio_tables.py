"""Parse shipped engine-sound lookup tables.

    python tools/engine/audio_tables.py --dump D:\\Games\\W6W-05 \
        --report build/tmp/audio_tables.json --list

`engmap.tbl` is consumed by `FUN_1407ccea0`: after the `WM4_ENGMAP` header and
entry count, it reads `count * 0x14` u32 values into one flat array. The file
holds ten `(engine_sound, group)` pairs per 20-int entry. `emtis.tbl` is read by
`FUN_1407ce100`; this tool records its header, section markers and source-file
names without inventing meanings for the numeric sections.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import car_catalog  # noqa: E402
import nub_audio  # noqa: E402

ENGMAP_MAGIC = "WM4_ENGMAP"
EMTIS_MAGIC = "EMTIS"
EMTIS_MARKER = 60026
ENTRY_INTS = 20


def number(token):
    if any(mark in token for mark in (".", "e", "E")):
        return float(token)
    return int(token)


def parse_engmap(path):
    with open(path, "r", encoding="cp932") as stream:
        lines = stream.read().splitlines()
    if len(lines) < 3 or lines[0].strip() != ENGMAP_MAGIC:
        raise ValueError("bad %s header: %s" % (ENGMAP_MAGIC, path))
    count = int(lines[1].strip())
    values = [int(token) for token in lines[2].split()]
    if len(values) != count * ENTRY_INTS:
        raise ValueError("%s: %d ints, expected %d" %
                         (path, len(values), count * ENTRY_INTS))
    entries = [values[i * ENTRY_INTS:(i + 1) * ENTRY_INTS]
               for i in range(count)]
    pairs = []
    by_id = {}
    for entry in entries:
        for index in range(0, ENTRY_INTS, 2):
            engine_sound, group = entry[index], entry[index + 1]
            pairs.append({"engine_sound": engine_sound, "group": group})
            if engine_sound in by_id and by_id[engine_sound] != group:
                raise ValueError("conflicting group for engine sound %d" %
                                 engine_sound)
            by_id[engine_sound] = group
    return {
        "magic": ENGMAP_MAGIC,
        "count": count,
        "entry_ints": ENTRY_INTS,
        "entries": entries,
        "pairs": pairs,
        "by_id": by_id,
        "groups": sorted(set(by_id.values())),
    }


def parse_emtis(path):
    with open(path, "r", encoding="cp932") as stream:
        lines = stream.read().splitlines()
    head = lines[0].split()
    if not head or head[0] != EMTIS_MAGIC:
        raise ValueError("bad %s header: %s" % (EMTIS_MAGIC, path))
    version = [int(token) for token in head[1:]]
    header = [number(token) for token in lines[1].split()]
    tokens = [number(token)
              for token in (lines[2] + " " + lines[3]).split()]
    sections = []
    start = None
    for index, token in enumerate(tokens + [EMTIS_MARKER]):
        if token != EMTIS_MARKER:
            continue
        if start is not None:
            sections.append({
                "marker": start - 1,
                "start": start,
                "length": index - start,
                "head": tokens[start:start + 8],
            })
        start = index + 1
    names = [line.strip() for line in lines[4:] if line.strip()]
    prefixes = ("Missfire", "Turbin", "Intake", "Engine")
    name_counts = {prefix: 0 for prefix in prefixes}
    for name in names:
        prefix = name.split("/")[0]
        if prefix in name_counts:
            name_counts[prefix] += 1
    return {
        "magic": EMTIS_MAGIC,
        "version": version,
        "header": header,
        "sections": sections,
        "names": names,
        "name_counts": name_counts,
    }


def collect(dump):
    root = os.path.join(dump, nub_audio.SOUND_DIR)
    engmap = parse_engmap(os.path.join(root, "engmap.tbl"))
    emtis = parse_emtis(os.path.join(root, "emtis.tbl"))
    engine_tones = nub_audio.parse_nub(os.path.join(root, "ENGINE.nub"))
    cars = []
    for entry in car_catalog.catalog(dump):
        engine_sound = entry["engine_sound"]
        group = engmap["by_id"].get(engine_sound)
        if group is None:
            raise ValueError("car %s: engine sound %d not in %s" %
                             (entry["model"], engine_sound, ENGMAP_MAGIC))
        cars.append({
            "model": entry["model"],
            "engine_sound": engine_sound,
            "group": group,
        })
    return {
        "engmap": engmap,
        "emtis": emtis,
        "engine_tone_count": engine_tones["tone_count"],
        "cars": cars,
    }


def report_text(data):
    engmap = data["engmap"]
    emtis = data["emtis"]
    cars = data["cars"]
    lengths = [section["length"] for section in emtis["sections"]]
    names = ", ".join("%s=%d" % item
                      for item in sorted(emtis["name_counts"].items()))
    sounds = [car["engine_sound"] for car in cars]
    return "\n".join([
        "%s: %d entries x %d ints, %d pairs, %d ids, groups %s" %
        (engmap["magic"], engmap["count"], engmap["entry_ints"],
         len(engmap["pairs"]), len(engmap["by_id"]), engmap["groups"]),
        "%s: version %s, %d sections %s, %d names (%s)" %
        (emtis["magic"], ".".join(map(str, emtis["version"])),
         len(emtis["sections"]), lengths, len(emtis["names"]), names),
        "ENGINE.nub tones: %d" % data["engine_tone_count"],
        "cars: %d, engine sound %d..%d" %
        (len(cars), min(sounds), max(sounds)),
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

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
