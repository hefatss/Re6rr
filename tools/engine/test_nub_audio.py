"""Self-check for the shipped nuSound2 .nub parser and WAV extractor."""

import argparse
import os
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nub_audio  # noqa: E402


def check(dump):
    root = os.path.join(dump, nub_audio.SOUND_DIR)
    bgm = nub_audio.parse_nub(os.path.join(root, "BGM.nub"))
    assert bgm["bank_id"] == 0 and bgm["tone_count"] == 30
    assert bgm["header_size"] == 0x2000 and bgm["data_size"] == 0x11a20
    first = bgm["tone_records"][0]
    assert first["rate"] == 22050 and first["channels"] == 1
    assert first["bits"] == 16 and first["length"] == 0x11a20
    assert first["data_offset"] == 0
    assert {row["data_offset"] for row in bgm["tone_records"]} == {0}
    assert all(row["loop"] for row in bgm["tone_records"])

    system = nub_audio.parse_nub(os.path.join(root, "SYSTEM.nub"))
    assert system["tone_count"] == 120
    assert system["tone_records"][1]["data_offset"] == 0x2a6f0
    assert system["tone_records"][1]["length"] == 0x25c6a
    assert sum(row["loop"] for row in system["tone_records"]) == 9

    strings = nub_audio.parse_string_table(
        os.path.join(root, "nuSound2ToneStrBGM.bin"), "tone")
    assert strings["bank_id"] == 0 and strings["count"] == 30
    assert strings["rows"][0]["name"] == "BGM_01"
    assert strings["rows"][0]["value"] == "sou_test_mono.wav"

    banks = nub_audio.parse_string_table(
        os.path.join(root, "nuSound2BankStr.bin"), "bank")
    assert banks["count"] == 8
    assert banks["rows"][0] == {"index": 0, "name": "BGM", "value": 1}
    assert banks["rows"][7]["name"] == "ENGINE"

    data = nub_audio.collect(dump)
    assert len(data["banks"]) == 149 and len(data["strings"]) == 9
    assert sum(len(bank["tone_records"])
               for bank in data["banks"].values()) == 781

    with tempfile.TemporaryDirectory() as directory:
        output = os.path.join(directory, "bgm_01.wav")
        row = nub_audio.extract(dump, "BGM.nub", 0, output)
        with wave.open(output, "rb") as stream:
            assert stream.getnchannels() == row["channels"]
            assert stream.getsampwidth() == row["bits"] // 8
            assert stream.getframerate() == row["rate"]
            assert stream.getnframes() * stream.getnchannels() * \
                   stream.getsampwidth() == row["length"]
    print("  149 banks, 781 tones, one WAV round-trip: all .nub checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
