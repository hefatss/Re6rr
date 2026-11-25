"""Self-check for engine sound bank/tone recovery."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_tables  # noqa: E402
import engine_sound  # noqa: E402


def check(dump):
    root = os.path.join(dump, engine_sound.nub_audio.SOUND_DIR)
    emtis = audio_tables.parse_emtis(os.path.join(root, "emtis.tbl"))
    layout = engine_sound.parse_layout(emtis)
    assert layout["counts"] == {
        "large": 96, "mid": 10, "small": 4, "single": 1,
        "sounds": 224, "groups": 5, "requests": 6,
    }
    assert [len(layout["arrays"][name]) for name in
            ("A", "B", "C", "D", "E", "F", "G", "H", "I")] == \
        [96, 96, 96, 10, 10, 4, 4, 1, 1]
    assert all(len(row) == 20 for row in layout["arrays"]["A"])
    assert all(len(row) == 10 for row in layout["arrays"]["C"])
    assert len(layout["sound_records"]) == 224
    assert all(len(row) == 47 for row in layout["sound_records"])
    assert len(layout["request_records"]) == 1
    assert layout["request_records"][0][1:] == [-1, -1]

    data = engine_sound.collect(dump)
    assert data["counts"]["sounds"] == 224
    assert data["engine_bank"] == 7 and data["engine_tone_count"] == 409
    assert data["missfire_bank"] == 4 and data["missfire_tone_count"] == 6
    assert data["request_tones"] == list(range(6))
    assert len(data["mappings"]) == 320

    groups = {}
    for item in data["mappings"]:
        groups[item["group"]] = groups.get(item["group"], 0) + 1
        assert len(item["layer_tones"]) == 16
        assert item["engine_sound"] == data["mappings"][
            item["car_type"] * 10 + item["tune"]]["engine_sound"]
    assert groups == {2: 64, 3: 192, 4: 64}
    assert sum(value == -1 for item in data["mappings"]
               for value in item["layer_tones"]) == 640
    assert all(tuple(item["layer_tones"][-2:]) == (-1, -1)
               for item in data["mappings"])

    first = data["mappings"][0]
    assert (first["car_type"], first["tune"], first["engine_sound"],
            first["group"]) == (0, 0, 0, 2)
    assert first["layer_tones"] == [5, 6, 7, 8, 9, 10, 11, 12,
                                    0, 0, 0, 0, 0, 0, -1, -1]
    tuned = data["mappings"][134]
    assert (tuned["car_type"], tuned["tune"], tuned["engine_sound"],
            tuned["group"]) == (13, 4, 95, 3)
    assert tuned["layer_tones"] == [169, 170, 171, 172, 173, 174, 175, 176,
                                    1, 0, 0, 3, 4, 0, -1, -1]
    print("  320 car/tune mappings, 224 engine sounds, bank 7/4 tones: all engine sound checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
