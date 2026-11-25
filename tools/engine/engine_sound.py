"""Recover engine-sound bank and tone selection from shipped tables.

    python tools/engine/engine_sound.py --dump D:\\Games\\W6W-05 \
        --report build/tmp/engine_sound.json --list

Native evidence in `wmn6r.exe`: `FUN_1407cca90` reads one `(engine_sound,
group)` pair from `engmap.tbl` using car type and tune level and passes both to
`FUN_1407d27f0`. That function builds 16 layer objects from `emtis.tbl` arrays:
`C[idx0][2..9]`, `E[idx1][1..3]`, `G[idx2][1..3]` and `J[idx3][1..2]`, where
`idx0..idx3` are the first four ints of each 0xbc-byte EMTIS record. The
`CSoundImpl` vtable at `0x1414f1188` starts playback in `FUN_1407d0450` with
bank table `[7, ?, ?, 4]`; `.nub` headers identify bank 7 as `ENGINE.nub` and
bank 4 as `MISSFIRE.nub`. No game data is stored in the repository.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_tables  # noqa: E402
import nub_audio  # noqa: E402

ENGINE_BANK = 7
MISSFIRE_BANK = 4
LAYER_COUNT = 16
REQUEST_COUNT = 6


def take(tokens, position, count, stride):
    total = count * stride
    flat = [int(tokens[position + index]) for index in range(total)]
    return ([flat[index * stride:(index + 1) * stride]
             for index in range(count)], position + total)


def parse_layout(emtis):
    header = emtis["header"]
    tokens = emtis["tokens"]
    sections = emtis["sections"]
    if len(sections) < 6 or len(header) < 43:
        raise ValueError("short emtis.tbl layout")
    large = int(header[33])
    mid = int(header[36])
    small = int(header[38])
    single = int(header[40])
    sounds = int(header[42])
    groups = int(header[12])
    requests = int(header[30])

    position = sections[0]["start"]
    arrays = {}
    for name, count, stride in (
            ("A", large, 20), ("B", large, 20), ("C", large, 10),
            ("D", mid, 15), ("E", mid, 4), ("F", small, 15),
            ("G", small, 4), ("H", single, 20), ("I", single, 5)):
        arrays[name], position = take(tokens, position, count, stride)
    if position != sections[0]["start"] + sections[0]["length"]:
        raise ValueError("emtis section 0 stride mismatch: %d" % position)

    records, position = take(tokens, sections[1]["start"], sounds, 47)
    if position != sections[1]["start"] + sections[1]["length"]:
        raise ValueError("emtis section 1 stride mismatch: %d" % position)

    section4 = sections[4]
    if section4["length"] != 204:
        raise ValueError("emtis section 4 length %d" % section4["length"])
    env_count, request_record_count = (
        int(tokens[section4["start"] + 200]),
        int(tokens[section4["start"] + 201]),
    )
    envelopes, position = take(tokens, sections[5]["start"],
                               env_count, 10)
    request_records, position = take(tokens, position,
                                     request_record_count, 3)

    return {
        "counts": {
            "large": large, "mid": mid, "small": small, "single": single,
            "sounds": sounds, "groups": groups, "requests": requests,
        },
        "arrays": arrays,
        "sound_records": records,
        "envelopes": envelopes,
        "request_records": request_records,
    }


def layer_tones(layout, engine_sound):
    if not 0 <= engine_sound < len(layout["sound_records"]):
        raise ValueError("engine sound %d outside EMTIS" % engine_sound)
    index0, index1, index2, index3 = layout["sound_records"][engine_sound][:4]
    arrays = layout["arrays"]
    if not (0 <= index0 < len(arrays["C"]) and
            0 <= index1 < len(arrays["E"]) and
            0 <= index2 < len(arrays["G"]) and
            0 <= index3 < len(layout["request_records"])):
        raise ValueError("engine sound %d: bad EMTIS indices %s" %
                         (engine_sound, (index0, index1, index2, index3)))
    return (arrays["C"][index0][2:10] +
            arrays["E"][index1][1:4] +
            arrays["G"][index2][1:4] +
            layout["request_records"][index3][1:3])


def collect(dump):
    root = os.path.join(dump, nub_audio.SOUND_DIR)
    engmap = audio_tables.parse_engmap(os.path.join(root, "engmap.tbl"))
    emtis = audio_tables.parse_emtis(os.path.join(root, "emtis.tbl"))
    layout = parse_layout(emtis)
    engine = nub_audio.parse_nub(os.path.join(root, "ENGINE.nub"))
    missfire = nub_audio.parse_nub(os.path.join(root, "MISSFIRE.nub"))

    if engine["bank_id"] != ENGINE_BANK or \
            missfire["bank_id"] != MISSFIRE_BANK:
        raise ValueError("bank ids: ENGINE=%d MISSFIRE=%d" %
                         (engine["bank_id"], missfire["bank_id"]))
    if engine["tone_count"] != int(emtis["header"][32]) or \
            missfire["tone_count"] != layout["counts"]["requests"]:
        raise ValueError("bank tone counts disagree with emtis.tbl")

    tones = {}
    for engine_sound in range(layout["counts"]["sounds"]):
        values = layer_tones(layout, engine_sound)
        if len(values) != LAYER_COUNT or any(
                value != -1 and not 0 <= value < engine["tone_count"]
                for value in values):
            raise ValueError("engine sound %d: bad tones %s" %
                             (engine_sound, values))
        tones[engine_sound] = values

    mappings = []
    for car_type, entry in enumerate(engmap["entries"]):
        for tune, (engine_sound, group) in enumerate(
                zip(entry[0::2], entry[1::2])):
            mappings.append({
                "car_type": car_type,
                "tune": tune,
                "engine_sound": engine_sound,
                "group": group,
                "layer_tones": tones[engine_sound],
            })
    return {
        "engmap_entries": engmap["count"],
        "counts": layout["counts"],
        "engine_bank": ENGINE_BANK,
        "engine_tone_count": engine["tone_count"],
        "missfire_bank": MISSFIRE_BANK,
        "missfire_tone_count": missfire["tone_count"],
        "request_tones": list(range(layout["counts"]["requests"])),
        "mappings": mappings,
    }


def report_text(data):
    mappings = data["mappings"]
    groups = {}
    for item in mappings:
        groups[item["group"]] = groups.get(item["group"], 0) + 1
    active = sum(value != -1 for item in mappings
                 for value in item["layer_tones"])
    return "\n".join([
        "%d car/tune mappings, %d engine sounds, groups %s" %
        (len(mappings), data["counts"]["sounds"],
         ", ".join("%s=%d" % item for item in sorted(groups.items()))),
        "bank %d ENGINE.nub tones %d, bank %d MISSFIRE.nub tones %d" %
        (data["engine_bank"], data["engine_tone_count"],
         data["missfire_bank"], data["missfire_tone_count"]),
        "%d/%d layer tones active, %d request tones" %
        (active, len(mappings) * LAYER_COUNT,
         len(data["request_tones"])),
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    data = collect(args.dump)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
    print(report_text(data) if args.list else
          report_text(data).splitlines()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
