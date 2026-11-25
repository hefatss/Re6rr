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
    assert len(engine_sound.RECORD_FIELD_TYPES) == 47
    first_record = layout["sound_records"][0]
    assert first_record[13] == 0.625 and first_record[14] == 225.0
    typed = layout["typed_sound_records"][0]
    assert typed[4] == 0xffffff06 and typed[12] == 9000
    assert typed[13] == 0.625 and typed[14] == 225.0
    assert engine_sound.s32(typed[4]) == -250
    assert all(engine_sound.u32(value) == value & 0xffffffff
               for value in first_record[:4])
    assert layout["runtime_constants"]["state_threshold"] == 1
    assert layout["runtime_constants"]["state_min_scale"] == 0.99
    assert layout["runtime_constants"]["request_amplitude"] == 5000

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
    layers = engine_sound.layer_envelopes(layout, 0)
    assert len(layers) == 16
    assert [item["envelope_source"] for item in layers] == \
        ["A"] * 4 + ["B"] * 4 + ["D"] * 3 + ["F"] * 3 + ["H"] * 2
    assert [item["tone"] for item in layers] == first["layer_tones"]
    assert layers[-1]["envelope"] == layout["envelopes"][0][:5]
    assert layers[-1]["rpm_limit"] is None
    assert engine_sound.envelope_output([0, 1000, 500, 800, 200], 500,
                                        1000, 2.0, 1.0,
                                        layout["header"]) == (824, 2)
    neutral = engine_sound.layer_outputs(layout, 0, 5000)
    assert len(neutral) == 16
    assert [item["tone"] for item in neutral] == first["layer_tones"]
    assert neutral[0]["pitch"] == 0 and neutral[0]["volume"] == -6625
    assert neutral[5]["pitch"] == 4936 and neutral[5]["volume"] == -5250
    shifted = engine_sound.layer_outputs(layout, 0, 5000,
                                         request_offset=1000)
    assert shifted[2]["pitch"] == 1 and shifted[5]["pitch"] == 4557
    assert [item["tone"] for item in shifted] == first["layer_tones"]
    print("  320 car/tune mappings, 224 engine sounds, bank 7/4 tones, 16 runtime layers: all engine sound checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
