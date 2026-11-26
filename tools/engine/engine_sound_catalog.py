"""Pack recovered engine-sound selection into a C-readable blob.

    python tools/engine/engine_sound_catalog.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/engine_sound.r6esnd

Only derived tables are written. The blob carries the 320 car/tune mappings
with their 16 layer tones and the 224 x 16 resolved layer envelopes from
`engine_sound.py`; no game data is committed.
"""

import argparse
import os
import struct

import engine_sound

MAGIC = b"R6ESND\0\1"
HEADER = struct.Struct("<8sIIIIII")
MAPPING = struct.Struct("<BBBBHH16i")
LAYER = struct.Struct("<BBBBHHi5iifiI")
SOURCES = {"A": 0, "B": 1, "D": 2, "F": 3, "H": 4}


def build(dump):
    data = engine_sound.collect(dump)
    mappings = data["mappings"]
    layers = data["envelope_layers"]
    sounds = data["counts"]["sounds"]
    tunes = len(mappings) // data["engmap_entries"]
    assert len(mappings) == data["engmap_entries"] * tunes
    assert len(layers) == sounds

    out = bytearray(HEADER.pack(MAGIC, 1, len(mappings), sounds, tunes,
                                sounds * engine_sound.LAYER_COUNT, 0))
    for item in mappings:
        out.extend(MAPPING.pack(item["car_type"], item["tune"],
                                item["group"], 0, item["engine_sound"], 0,
                                *item["layer_tones"]))
    for sound in range(sounds):
        for row in layers[str(sound)]:
            has_rpm = row["rpm_limit"] is not None
            has_scale = row["scale"] is not None
            out.extend(LAYER.pack(
                row["layer"], SOURCES[row["envelope_source"]],
                (1 if has_rpm else 0) | (2 if has_scale else 0), 0,
                row["envelope_index"], 0, row["tone"], *row["envelope"],
                row["rpm_limit"] if has_rpm else 0,
                row["scale"] if has_scale else 0.0, row["base"], 0))
    return bytes(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    blob = build(args.dump)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    header = HEADER.unpack_from(blob)
    print("%s: %d mappings, %d engine sounds, %d layers, %d bytes" %
          (args.out, header[2], header[3], header[5], len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
