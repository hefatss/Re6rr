"""Model the scene-config bridge from Environment.Lua camid to .EES camera slots.

    python tools/engine/scene_bridge.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/scene_bridge.json

Native chain, VA in `wmn6r.exe` (image base 0x140000000):

  0x1401e3640  Environment.Lua CAMID -> scene struct +0x24
  0x1401eaab0  scene struct +0x24 -> config object +0x70
  0x1401d7590  config object = scene base + 0x740
  0x1401f1f20  config +0x70 selects the CamData.EES slot and is copied to
               the loader object at +0x48; all five files load at
               base + 0x2d78 + slot * 0x1b0
  0x1401e1ff0  config +0x70 indexes 255-entry camera arrays; frame lookup
               returns the FIRST matching record (0..254, else -1)

`FUN_1401c8f60` uses a different selector: it scans the same start/duration/
exact fields but keeps the LAST match. Both models are checked here.
"""

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import ees_scene  # noqa: E402
import scene_config  # noqa: E402
import story_catalog  # noqa: E402

CONFIG_OFFSET = 0x740
CONFIG_CAMID = 0x70
CONTAINER_BASE = 0x2D78
CONTAINER_STRIDE = 0x1B0
CONTAINER_COUNT = 5
LOADER_CAMID = 0x48


def write_camid(scene, config, camid=None):
    """Model 0x1401eaab0: scene +0x24 -> config +0x70."""
    if camid is None:
        camid = int.from_bytes(scene[scene_config.SLOT_OFFSETS["cam_id"]:
                                    scene_config.SLOT_OFFSETS["cam_id"] + 4],
                               "little", signed=True)
    config[CONFIG_CAMID:CONFIG_CAMID + 4] = camid.to_bytes(
        4, "little", signed=True)
    return camid


def container_offset(slot):
    """0x1401f1f20: base + 0x2d78 + slot * 0x1b0."""
    if not 0 <= slot < CONTAINER_COUNT:
        raise ValueError("camera slot out of range: %d" % slot)
    return CONTAINER_BASE + slot * CONTAINER_STRIDE


def runtime_camera_at_frame(records, frame):
    """0x1401e1ff0: first matching record index, else -1."""
    for index, record in enumerate(records):
        if record["type"] == ees_fields.CAMERA_EMPTY:
            continue
        start, end, exact = record["start"], record["end"], record["exact"]
        if end is None:
            continue
        if exact == 1:
            if start == frame:
                return index
        elif start <= frame <= end:
            return index
    return -1


def read_camera(dump, episode, slot):
    directory = os.path.join(dump, ees_scene.SCENE_DIR, episode, "FrontEvent")
    name = "CamData.EES" if slot == -1 else "CamData%d.EES" % slot
    path = os.path.join(directory, name)
    with open(path, "rb") as stream:
        raw = stream.read()
    return raw, ees_fields.camera_rows(raw, ees_scene.parse_ees(raw))


def build(dump):
    rows = []
    root = os.path.join(dump, ees_scene.SCENE_DIR)
    for entry in sorted(os.listdir(root)):
        path = os.path.join(root, entry)
        if not os.path.isdir(path) or not entry.startswith("ESeries_"):
            continue
        values = story_catalog.parse_environment(path)
        if not values["present"]:
            continue
        camid = values["cam_id"]
        scene = scene_config.write_scene(values)
        config = bytearray(0x800)
        copied = write_camid(scene, config)
        base_raw, _ = read_camera(dump, entry, -1)
        selected_raw, records = read_camera(dump, entry, camid)
        samples = []
        for record in records:
            if record["type"] == ees_fields.CAMERA_EMPTY:
                continue
            frame = record["start"]
            samples.append({
                "frame": frame,
                "runtime": runtime_camera_at_frame(records, frame),
                "scene": ees_fields.camera_at_frame(records, frame),
            })
            if len(samples) >= 4:
                break
        rows.append({
            "episode": entry,
            "cam_id": camid,
            "copied_camid": copied,
            "config_camid": int.from_bytes(config[CONFIG_CAMID:
                                                 CONFIG_CAMID + 4],
                                           "little", signed=True),
            "container_offset": container_offset(camid),
            "loader_camid": LOADER_CAMID,
            "base_matches_selected": hashlib.sha256(base_raw).digest() ==
                                     hashlib.sha256(selected_raw).digest(),
            "samples": samples,
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", help="write JSON report")
    args = parser.parse_args()

    rows = build(args.dump)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf8") as stream:
            json.dump(rows, stream, indent=2, ensure_ascii=False)
    print("episodes: %d, camids: %s, base==selected: %d" %
          (len(rows), sorted(set(row["cam_id"] for row in rows)),
           sum(1 for row in rows if row["base_matches_selected"])))
    for row in rows[:3]:
        print("  %-18s camid %d slot 0x%x %s" %
              (row["episode"], row["cam_id"], row["container_offset"],
               row["samples"][:2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
