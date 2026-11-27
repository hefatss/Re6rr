"""Pack shipped camera-file identity facts into an R6SCI blob.

    python tools/engine/scene_identity_catalog.py \
        --dump D:\\Games\\W6W-05 --out build/tmp/scene_identity.r6sci

The only derived value is equality of CamData.EES and CamData<camid>.EES bytes
for each shipped Environment.Lua episode. No camera field is reinterpreted.
"""

import argparse
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

import scene_bridge  # noqa: E402

MAGIC = b"R6SCI\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s4I")
RECORD = struct.Struct("<IIi")


def collect(dump):
    return [{"episode": row["episode"],
             "cam_id": row["cam_id"],
             "matches": int(row["base_matches_selected"])}
            for row in scene_bridge.build(dump)]


def build(rows):
    strings = bytearray()
    strings_off = HEADER.size + RECORD.size * len(rows)
    offsets = {}

    def intern(value):
        encoded = value.encode("utf8") + b"\0"
        if encoded not in offsets:
            offsets[encoded] = strings_off + len(strings)
            strings.extend(encoded)
        return offsets[encoded]

    records = bytearray()
    for row in rows:
        records.extend(RECORD.pack(intern(row["episode"]), row["matches"],
                                   row["cam_id"]))
    header = HEADER.pack(MAGIC, VERSION, len(rows), strings_off, len(strings))
    return header + bytes(records + strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = collect(args.dump)
    blob = build(rows)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%d episodes, %d bytes: %s" % (len(rows), len(blob), args.out))


if __name__ == "__main__":
    main()
