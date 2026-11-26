"""Pack shipped Environment.Lua values into an R6SES blob.

    python tools/engine/scene_env_catalog.py \
        --dump D:\\Games\\W6W-05 --out build/tmp/scene_env.r6ses

Rows come from data_jp/scene/ESeries_* Environment.Lua files in shipped order.
The core reads only the derived blob; it never opens a file or parses Lua.
"""

import argparse
import glob
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

MAGIC = b"R6SES\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s14I")
ROW = struct.Struct("<10I")


def collect(dump):
    import story_catalog  # noqa: E402

    pattern = os.path.join(dump, "data_jp", "scene", "ESeries_*")
    rows = []
    for path in sorted(glob.glob(pattern)):
        if not os.path.isdir(path):
            continue
        value = story_catalog.parse_environment(path)
        rows.append({"name": os.path.basename(path),
                     "present": value["present"],
                     "stage": value["stage"],
                     "stage_root": value["stage_root"],
                     "stage_day": value["stage_day"],
                     "cam_id": value["cam_id"],
                     "actors": list(value["actors"])})
    assert len(rows) == 122, len(rows)
    return rows


def summarize(rows):
    present = [row for row in rows if row["present"]]
    all_actors = [value for row in rows for value in row["actors"]]
    actors = [value for row in present for value in row["actors"]]
    nonzero = [value for value in actors if value]
    stages = [row["stage"] for row in present]
    return {
        "dirs": len(rows),
        "present": len(present),
        "actor_slots": len(all_actors),
        "present_slots": len(actors),
        "nonzero": len(nonzero),
        "unique_actors": len(set(nonzero)),
        "actor_min": min(all_actors),
        "actor_max": max(all_actors),
        "stages": len(stages),
        "unique_stages": len(set(stages)),
        "stage_min": min(stages),
        "stage_max": max(stages),
    }


def build(rows, summary=None):
    summary = summary or summarize(rows)
    strings_off = HEADER.size + ROW.size * len(rows)
    strings_size = sum(len(row["name"]) + 1 for row in rows)
    strings = bytearray()
    offsets = []
    for row in rows:
        offsets.append(strings_off + len(strings))
        strings.extend(row["name"].encode("ascii") + b"\0")

    payload = b"".join(
        ROW.pack(offsets[index], row["present"], row["stage"],
                 row["stage_root"], row["stage_day"], row["cam_id"],
                 *row["actors"])
        for index, row in enumerate(rows))
    return HEADER.pack(
        MAGIC, VERSION, summary["dirs"], summary["present"],
        summary["actor_slots"], summary["present_slots"],
        summary["nonzero"], summary["unique_actors"],
        summary["actor_min"], summary["actor_max"], summary["stages"],
        summary["unique_stages"], summary["stage_min"],
        summary["stage_max"], strings_size) + payload + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = collect(args.dump)
    summary = summarize(rows)
    assert (summary["dirs"], summary["present"], summary["actor_slots"],
            summary["nonzero"], summary["unique_actors"],
            summary["stage_min"], summary["stage_max"]) == (
                122, 59, 488, 186, 36, 1, 149), summary
    blob = build(rows, summary)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d dirs, %d present, %d actor slots, %d nonzero, %d bytes" %
          (args.out, summary["dirs"], summary["present"],
           summary["actor_slots"], summary["nonzero"], len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
