"""Self-check for shipped engine-sound lookup table parsing."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_tables  # noqa: E402


def check(dump):
    data = audio_tables.collect(dump)
    engmap = data["engmap"]
    emtis = data["emtis"]

    assert engmap["magic"] == "WM4_ENGMAP"
    assert engmap["count"] == 32 and engmap["entry_ints"] == 20
    assert len(engmap["entries"]) == 32
    assert len(engmap["pairs"]) == 320
    assert len(engmap["by_id"]) == 224
    assert engmap["groups"] == [2, 3, 4]
    assert engmap["by_id"][0] == 2
    assert engmap["by_id"][13] == 4
    assert engmap["by_id"][20] == 4

    assert emtis["magic"] == "EMTIS"
    assert emtis["version"] == [3, 3, 17]
    assert len(emtis["sections"]) == 7
    assert [section["marker"] for section in emtis["sections"]] == \
        [0, 5092, 15621, 15772, 16033, 16238, 16364]
    assert [section["length"] for section in emtis["sections"]] == \
        [5091, 10528, 150, 260, 204, 125, 0]
    assert len(emtis["names"]) == 416
    assert emtis["name_counts"] == {"Missfire": 6, "Turbin": 3,
                                    "Intake": 2, "Engine": 405}
    assert len(engmap["by_id"]) == emtis["header"][42]
    assert data["engine_tone_count"] == emtis["header"][32] == 409

    cars = data["cars"]
    assert len(cars) == 151
    assert min(car["engine_sound"] for car in cars) == 0
    assert max(car["engine_sound"] for car in cars) == 31
    by_model = {car["model"]: car for car in cars}
    assert by_model["PLC_ZR1"]["engine_sound"] == 13
    assert by_model["PLC_ZR1"]["group"] == 4
    assert by_model["PLC_ZN6"]["engine_sound"] == 20
    assert by_model["PLC_ZN6"]["group"] == 4
    print("  32 engmap entries, 7 emtis sections, 151 cars: all table checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
