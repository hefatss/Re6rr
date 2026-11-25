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
