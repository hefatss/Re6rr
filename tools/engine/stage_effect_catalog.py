"""Pack shipped stage-effect symbolic sounds into a C-readable blob.

    python tools/engine/stage_effect_catalog.py --dump D:\\Games\\W6W-05 \
        --out build\\tmp\\stage_effect.r6stg

Rows come from tools/engine/stage_effect_sound.py: the two native tone ids in
FUN_1401b0cd0 and the three shipped parameter scripts. No game data is
committed; the output is derived data for the freestanding core.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import stage_effect_sound  # noqa: E402

MAGIC = b"R6STG\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIII")
RECORD = struct.Struct("<IIIIIHHHHfff")


def collect(dump):
    return stage_effect_sound.build(dump)


def build(rows):
    items = []
    for row in rows:
        resolved = row["resolved"]
        items.append((
            row["set"] or "", row["symbol"], row["file"],
            resolved["tone_name"] if resolved else "",
            resolved["wav"] if resolved else "",
            resolved["bank"] if resolved else 0,
            resolved["tone"] if resolved else -1,
            row["native_tone"] if row["native_tone"] is not None else -1,
            row["loop"] if row["loop"] is not None else -1,
            *(row["position"] or (0.0, 0.0, 0.0)),
        ))

    strings_off = HEADER.size + len(items) * RECORD.size
    strings = bytearray(b"\0")
    offsets = {b"": strings_off}

    def intern(value):
        encoded = value.encode("utf8") + b"\0"
        if encoded not in offsets:
            offsets[encoded] = strings_off + len(strings)
            strings.extend(encoded)
        return offsets[encoded]

    records = bytearray()
    for item in items:
        records.extend(RECORD.pack(*[intern(value) for value in item[:5]],
                                   *item[5:]))

    return (HEADER.pack(MAGIC, VERSION, len(items), strings_off, len(strings),
                        0, 0) + bytes(records) + bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = collect(args.dump)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d stage-effect sounds, %d bytes" %
          (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
