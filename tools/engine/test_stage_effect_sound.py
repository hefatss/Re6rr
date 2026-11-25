"""Checks shipped stage-effect symbolic sound names against native ids."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import stage_effect_sound as ses  # noqa: E402


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def run(dump, failures):
    rows = ses.build(dump)
    check(len(rows) == 6, "stage-effect entry count", failures)
    check(all(row["resolved"] for row in rows), "symbol resolution",
          failures)
    check(set(row["set"] for row in rows) == {
        "SET_PA_N_hanabi_A", "SET_PA_N_hanabi_B",
        "SET_PA_N_hanabi_KKS_A"}, "shipped effect sets", failures)
    symbols = {}
    for row in rows:
        symbols[row["symbol"]] = row["resolved"]
        check(len(row["position"]) == 3, "sound position width", failures)
        check(row["loop"] == 0, "one-shot loop flag", failures)
    check(set(symbols) == set(ses.NATIVE_TONE_IDS), "symbol inventory",
          failures)
    for symbol, native_tone in ses.NATIVE_TONE_IDS.items():
        resolved = symbols[symbol]
        check(resolved["bank"] == 3 and resolved["bank_name"] == "RACE",
              "%s bank" % symbol, failures)
        check(resolved["tone"] == native_tone,
              "%s native tone id" % symbol, failures)
    check(symbols["NUD_TONE_RACE_HANABI1"]["wav"] == "hanabi1.wav",
          "hanabi1 wav", failures)
    check(symbols["NUD_TONE_RACE_HANABI2"]["wav"] == "hanabi2.wav",
          "hanabi2 wav", failures)
    unknown = ses.resolve_symbolic("NUD_TONE_RACE_MISSING",
                                   audio_events.bank_names(dump),
                                   {"RACE": audio_events.tone_names(
                                       dump, "RACE")})
    check(unknown is None, "unknown tone name", failures)
    bad = ses.resolve_symbolic("NO_PREFIX", [], {})
    check(bad is None, "non-symbolic name", failures)
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
    print("stage_effect_sound checks: %s" % ("FAIL" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
