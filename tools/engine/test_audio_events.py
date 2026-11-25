"""Checks for shipped BGM ids, bank strings and Lua sound bindings."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def run(dump, failures):
    sections = audio_events.build(dump)
    banks = dict(sections["banks"])
    expected = ["BGM", "MOVIE", "SYSTEM", "RACE", "MISSFIRE",
                "OTHERCAR", "RIVALCAR", "ENGINE"]
    check([banks[index] for index in range(8)] == expected,
          "bank string table", failures)

    bgm = sections["bgm"]
    check(len(bgm) == 142, "bgm count", failures)
    check(bgm[0]["name"] == "01.SYSTEMBGM_ENTRY", "bgm 0 name", failures)
    check(bgm[0]["path"] == "./data/sound/BGM/SYS_01B.nub",
          "bgm 0 path", failures)
    check(bgm[audio_events.BGM_NO_SOUND]["name"].strip() == "NO BGM",
          "bgm no-sound name", failures)
    check(bgm[audio_events.BGM_RANDOM]["name"].strip() == "RANDOM",
          "bgm random name", failures)
    check(audio_events.bgm_by_name(bgm, "SYSTEMBGM_STORY") == 1,
          "bgm name lookup", failures)
    check(audio_events.bgm_by_name(bgm, "not shipped") == -1,
          "bgm name miss", failures)
    check(all(row["path"] and row["name"] for row in bgm),
          "bgm rows complete", failures)

    bindings = dict((row["name"], row) for row in sections["bindings"])
    check(len(bindings) == 12, "binding count", failures)
    check(bindings["PlaySE"]["bank_name"] == "SYSTEM",
          "PlaySE bank", failures)
    check(bindings["PlaySE"]["tone"] is None, "PlaySE tone is an argument",
          failures)
    check(bindings["PlaySEOfBank"]["bank"] is None,
          "PlaySEOfBank bank is an argument", failures)
    check(bindings["PlaySEDecide"]["tone_name"] == "SELECT",
          "decide tone", failures)
    check(bindings["PlaySECancel"]["tone_name"] == "CANCEL",
          "cancel tone", failures)
    check(bindings["PlaySEMove"]["tone_name"] == "CURSOR",
          "move tone", failures)
    check(bindings["StopBGM"]["call"] == "stopBgm",
          "stop BGM binding", failures)

    tones = audio_events.tone_names(dump, "SYSTEM")
    check(len(tones) == 120, "SYSTEM tone count", failures)
    check(tones[47][1] == "select.wav", "SYSTEM tone 47 wav", failures)

    playback = sections["dispatch"]["playback"]
    check(playback["bgm_stream_handle"] == 0 and
          playback["voice_slots"] == 0x40 and
          playback["voice_stride"] == 0xA0 and
          playback["voice_meta_base"] == 0x2800 and
          playback["voice_meta_stride"] == 0xC,
          "nuSound2 playback ABI", failures)
    check(playback["bank_set_errors"] == {
        "bad_index": 0x8000001E, "bad_format": 0x8000001D,
        "null_data": 0x80000024, "already_set": 0x80000021,
        "voice_fail": 0x80000026, "stream_fail": 0x80000027},
        "nuSound2 bank-set errors", failures)

    dispatch = sections["dispatch"]
    check(dispatch["bank_table"] == {
        "stride": 0x20, "handle": 0x18, "state": 0x1C, "ready": 3},
        "bank table ABI", failures)
    check(dispatch["requests"]["count"] == 34, "request id count", failures)
    check(dispatch["requests"]["loop_slot"] == 0x21 < 34,
          "scene loop slot", failures)
    check(dispatch["key_on_defaults"]["volume"] == 1.0 and
          dispatch["key_on_defaults"]["pan"] == 0.0 and
          dispatch["key_on_defaults"]["flags"] == 0,
          "KeyOn defaults", failures)
    mixer = sections["mixer"]
    check(mixer["bus_count"] == 0x44 and mixer["bus_stride"] == 0x48 and
          mixer["fields"] == {"mode": 0x10, "volume": 0x00,
                              "target": 0x18, "step": 0x1C, "frames": 0x14} and
          mixer["fade_mode"] == 2 and mixer["invalid_bus"] == 0x80000001 and
          list(mixer["db_calibration"]) == [0x1C20, 0x1C28, 0x1C2C],
          "mixer ABI", failures)
    lo, mid, hi = -96.0, 6.0, 2.0
    for db in (-96.0, -48.0, 0.0, 5.999, 6.0, 12.0, 24.0):
        volume = audio_events.decibels_to_volume(db, lo, mid, hi)
        check(abs(audio_events.volume_to_decibels(volume, lo, mid, hi) - db)
              < 0.001, "dB round trip %s" % db, failures)
    check(audio_events.decibels_to_volume(-100.0, lo, mid, hi) == 0.0 and
          audio_events.volume_to_decibels(0.0, lo, mid, hi) == lo,
          "dB clamps", failures)
    state = {"volume": 1.0, "target": 1.0, "step": 0.0, "frames": 0,
             "mode": 0}
    audio_events.bus_fade(state, 2.0, 10)
    check(state["target"] == 2.0 and abs(state["step"] - 0.1) < 1e-6 and
          state["frames"] == 10 and state["mode"] == 2,
          "bus fade over frames", failures)
    audio_events.bus_fade(state, 0.5, 0)
    check(state["volume"] == 0.5 and state["mode"] == 0 and
          state["frames"] == 0, "bus fade immediate", failures)

    config = dispatch["config"]
    check(config["size"] == 0xA50 and config["header_size"] == 0x50,
          "config.bin header", failures)
    check(config["float_offset"] == 0x70, "config.bin float offset", failures)
    check(config["sections"] == [(4, 0x470), (5, 0x4B0), (0x21, 0x500),
                                 (10, 0x710), (8, 0x850), (8, 0x950)],
          "config.bin sections", failures)

    scripts = 0
    for directory, _, names in os.walk(dump):
        for name in names:
            if not name.endswith(".lua"):
                continue
            scripts += 1
            with open(os.path.join(directory, name), "rb") as stream:
                text = stream.read()
            if b"PlaySE" in text or b"PlayBGM" in text:
                failures.append("shipped Lua calls sound binding")
                break
    check(scripts > 4000, "Lua inventory", failures)
    return len(failures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    failures = []
    run(args.dump, failures)
    for failure in failures:
        print("FAIL " + failure)
    print("audio_events checks: %s" % ("FAIL" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
