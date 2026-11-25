"""Resolve shipped stage-effect sound parameters to native bank/tone ids.

    python tools/engine/stage_effect_sound.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/stage_effect_sound.json

`FUN_1401b0cd0` builds two hard-coded entries from the literals
`NUD_TONE_RACE_HANABI1`/`NUD_TONE_RACE_HANABI2` with tone ids `0xe` and `0xf`.
Three shipped `data/effect/stage_effect/sound/*/parameter/*.lua` files declare
the same symbolic names. Resolving them through `nuSound2BankStr.bin` and
`nuSound2ToneStrRACE.bin` gives bank 3 (RACE), tones 14/15 (`hanabi1.wav`,
`hanabi2.wav`). No game data is stored in the repository.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402

EFFECT_DIR = os.path.join("data", "effect", "stage_effect", "sound")
# Native literal tone ids paired with the two symbolic names in FUN_1401b0cd0.
NATIVE_TONE_IDS = {"NUD_TONE_RACE_HANABI1": 0x0E,
                   "NUD_TONE_RACE_HANABI2": 0x0F}

PATH_RE = re.compile(rb'path\s*=\s*"([^"]+)"')
SET_RE = re.compile(rb'name\s*=\s*"([^"]+)"')
POS_RE = re.compile(rb'pos\s*=\s*\{([^}]+)\}')
LOOP_RE = re.compile(rb'loop\s*=\s*(\d+)')


def resolve_symbolic(symbol, banks, tone_cache):
    """Map NUD_TONE_<BANK>_<NAME> through shipped nuSound2 string tables."""
    if not symbol.startswith("NUD_TONE_"):
        return None
    rest = symbol[len("NUD_TONE_"):]
    for bank_id, bank_name in banks:
        prefix = bank_name + "_"
        if not rest.upper().startswith(prefix.upper()):
            continue
        tone_name = rest[len(prefix):].upper()
        for tone_id, (name, wav) in enumerate(tone_cache[bank_name]):
            if name.upper() == tone_name:
                return {"bank": bank_id, "bank_name": bank_name,
                        "tone": tone_id, "tone_name": name, "wav": wav}
    return None


def build(dump):
    banks = audio_events.bank_names(dump)
    tone_cache = {}
    for _, bank_name in banks:
        tone_cache[bank_name] = audio_events.tone_names(dump, bank_name)
    root = os.path.join(dump, EFFECT_DIR)
    rows = []
    for directory, _, names in os.walk(root):
        for name in sorted(names):
            if not name.endswith(".lua"):
                continue
            rel = os.path.relpath(os.path.join(directory, name),
                                  dump).replace("\\", "/")
            with open(os.path.join(directory, name), "rb") as stream:
                raw = stream.read()
            sets = [value.decode("latin1")
                    for value in SET_RE.findall(raw)]
            paths = [value.decode("latin1")
                     for value in PATH_RE.findall(raw)]
            positions = [[float(value) for value in group.split(b",")]
                         for group in POS_RE.findall(raw)]
            loops = [int(value) for value in LOOP_RE.findall(raw)]
            for index, symbol in enumerate(paths):
                resolved = resolve_symbolic(symbol, banks, tone_cache)
                rows.append({
                    "file": rel,
                    "set": sets[0] if sets else None,
                    "symbol": symbol,
                    "position": positions[index] if index < len(positions)
                    else None,
                    "loop": loops[index] if index < len(loops) else None,
                    "native_tone": NATIVE_TONE_IDS.get(symbol),
                    "resolved": resolved,
                })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", help="write JSON report")
    args = parser.parse_args()

    rows = build(args.dump)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf8") as stream:
            json.dump(rows, stream, indent=2, ensure_ascii=False)
    print("stage-effect sound entries: %d, unresolved: %d" %
          (len(rows), sum(1 for row in rows if row["resolved"] is None)))
    for row in rows[:6]:
        resolved = row["resolved"] or {}
        print("  %-24s %-22s bank %s tone %s %s" %
              (row["set"], row["symbol"], resolved.get("bank", "?"),
               resolved.get("tone", "?"), resolved.get("wav", "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
