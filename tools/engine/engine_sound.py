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
bank 4 as `MISSFIRE.nub`. `FUN_1407cd490` proves the 47 fields of each 0xbc-byte
EMTIS record are read as int32, uint32 and float32; float tokens are preserved
so native `MOVSS` fields keep their value. No game data is stored in the
repository.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_tables  # noqa: E402
import nub_audio  # noqa: E402

ENGINE_BANK = 7
MISSFIRE_BANK = 4
LAYER_COUNT = 16
REQUEST_COUNT = 6

# FUN_1407cd490 reads each 0xbc-byte EMTIS sound record with fixed stream
# extraction operators: i=int32, u=uint32, f=float32. Offset +0x30 is uint32;
# float fields start at +0x34. Keeping float tokens as floats is required:
# native MOVSS reads the stored float bit pattern.
RECORD_FIELD_TYPES = (
    "iiii" + "u" * 9 + "f" * 6 + "u" + "f" * 7 + "u" + "f" * 8 +
    "u" + "f" + "ii" + "f" * 7
)


def u32(token):
    if isinstance(token, int):
        return token & 0xffffffff
    return struct.unpack("<I", struct.pack("<f", token))[0]


def s32(token):
    value = u32(token)
    return value - 0x100000000 if value & 0x80000000 else value


def runtime_constants(emtis):
    tokens = emtis["tokens"]
    sections = emtis["sections"]
    if len(sections) < 6:
        raise ValueError("short emtis.tbl for runtime constants")
    section4 = sections[4]
    section5 = sections[5]
    tail4 = tokens[section4["start"] + section4["length"] - 12:
                   section4["start"] + section4["length"]]
    tail5 = tokens[section5["start"] + section5["length"] - 8:
                   section5["start"] + section5["length"]]
    if len(tail4) != 12 or len(tail5) != 8:
        raise ValueError("bad emtis runtime constant tail")
    names4 = ("request_amplitude", "request_pitch", "state_threshold",
              "state_min_scale", "pitch_divisor", "rpm_scale",
              "rpm_base", "rpm_step", "envelope_count", "request_count",
              "curve_count", "curve_kind")
    names5 = ("boost_limit", "boost_rate", "boost_decay_ms",
              "boost_decay_rate", "boost_count", "boost_time",
              "boost_rise", "boost_fall")
    return dict(list(zip(names4, tail4)) + list(zip(names5, tail5)))


def take(tokens, position, count, stride):
    total = count * stride
    flat = [tokens[position + index] for index in range(total)]
    return ([flat[index * stride:(index + 1) * stride]
             for index in range(count)], position + total)


def typed_record(values):
    if len(values) != len(RECORD_FIELD_TYPES):
        raise ValueError("sound record has %d fields" % len(values))
    result = []
    for token, kind in zip(values, RECORD_FIELD_TYPES):
        if kind == "f":
            result.append(float(token))
        elif kind == "u":
            result.append(u32(token))
        else:
            result.append(int(token))
    return result


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
        "header": header,
        "counts": {
            "large": large, "mid": mid, "small": small, "single": single,
            "sounds": sounds, "groups": groups, "requests": requests,
        },
        "arrays": arrays,
        "sound_records": records,
        "typed_sound_records": [typed_record(record) for record in records],
        "envelopes": envelopes,
        "request_records": request_records,
        "runtime_constants": runtime_constants(emtis),
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


def layer_envelopes(layout, engine_sound):
    """Resolve the 16 layer envelopes used by FUN_1407d2b50.

    Each 10-byte envelope chunk is `(start, peak, centre, fall_start,
    fall_end)`. Sources A/B/D/F come from EMTIS section 0; the last source is
    the section-5 H array indexed by the request record. `FUN_1407d0dc0` reads
    one chunk per layer and advances 10 bytes. `rpm_limit`/`scale` come from
    the typed 0xbc-byte record; the last group has no rpm gate.
    """
    if not 0 <= engine_sound < len(layout["typed_sound_records"]):
        raise ValueError("engine sound %d outside EMTIS" % engine_sound)
    cfg = layout["typed_sound_records"][engine_sound]
    arrays = layout["arrays"]
    i0, i1, i2, i3 = cfg[:4]
    c, e, g = arrays["C"][i0], arrays["E"][i1], arrays["G"][i2]
    request = layout["request_records"][i3]

    groups = (
        ("A", c[0], arrays["A"][c[0]], 4, 0x30, 0x34, 0x14),
        ("B", c[1], arrays["B"][c[1]], 4, 0x4c, 0x50, 0x18),
        ("D", e[0], arrays["D"][e[0]], 3, 0x90, 0x94, 0x1c),
        ("F", g[0], arrays["F"][g[0]], 3, 0x6c, 0x70, 0x20),
        ("H", request[0], layout["envelopes"][request[0]], 2, None, None, 0x24),
    )
    tones = layer_tones(layout, engine_sound)
    result = []
    position = 0
    for name, index, values, count, rpm_offset, scale_offset, base_offset in groups:
        if len(values) != count * 5:
            raise ValueError("engine sound %d: %s[%d] has %d values" %
                             (engine_sound, name, index, len(values)))
        for layer in range(count):
            result.append({
                "layer": position,
                "tone": tones[position],
                "envelope_source": name,
                "envelope_index": index,
                "envelope": values[layer * 5:(layer + 1) * 5],
                "rpm_limit": (s32(cfg[rpm_offset // 4])
                              if rpm_offset is not None else None),
                "scale": (cfg[scale_offset // 4]
                          if scale_offset is not None else None),
                "base": s32(cfg[4]) + s32(cfg[base_offset // 4]),
            })
            position += 1
    return result


def envelope_output(envelope, rpm, amplitude, volume_base, volume_scale,
                    header):
    """Port FUN_1407d0dc0: pitch curve plus detune-derived volume."""
    start, peak, centre, fall_start, fall_end = envelope
    if rpm < start:
        level = 0.0
    elif rpm < peak:
        level = (rpm - start) / (peak - start)
    elif fall_start < rpm:
        level = ((rpm - fall_end) / (fall_start - fall_end)
                 if rpm < fall_end else 0.0)
    else:
        level = 1.0
    pitch = int((level ** header[2]) * amplitude) if level > 0 else 0
    detune = (rpm - centre) * volume_scale / header[0]
    volume = int((2.0 ** detune) * volume_base)
    return pitch, volume


def clamp_volume(value):
    """Native converts positive dB to zero and clamps the floor at -10000."""
    if value >= 1:
        return 0
    return max(value, -10000)


def layer_outputs(layout, engine_sound, rpm, state=None, request_offset=0):
    """Evaluate the 16 engine layers of FUN_1407d2b50.

    `state` supplies runtime values the shipped tables do not fix: `rpm`
    (+0xfc), five base-volume ints, smoothed floats, the engine-brake flag,
    throttle, layer base volumes and two curve scales. `request_offset` is the
    random-driven result of FUN_1407d2520. Defaults give the neutral state.
    """
    lexical = layout["sound_records"][engine_sound]
    header = layout["header"]
    constants = layout["runtime_constants"]
    layers = layer_envelopes(layout, engine_sound)
    s = state or {}
    rpm_value = int(rpm)
    adjusted = rpm_value + int(request_offset)
    current = int(s.get("rpm", rpm_value))
    base = list(s.get("base", [0] * 5))
    layer_base = list(s.get("layer_base", [1.0] * LAYER_COUNT))
    flag = bool(s.get("flag", False))
    throttle = float(s.get("throttle", 0.0))
    floors = s.get("floors", [(0, 0, 0)] * 3)

    # Native reads these engine-state fields with MOVSS; the lexical EMTIS
    # tokens carry the same float bit patterns even where the file parser
    # extracted them as uint32.
    f34 = max(float(lexical[13]), float(s.get("smooth34", 0.0)))
    f4f = float(s.get("smooth4f", 0.0))
    f20 = max(float(lexical[8]), float(s.get("smooth20", 0.0)))
    f134 = float(s.get("f134", 0.0))
    f2d = float(s.get("f2d", 0.0))
    if not flag:
        smoothed = [f20, f134, f2d]
        for index, (low, high, floor) in enumerate(floors[:3]):
            value = (high + low - floor) * throttle + floor
            smoothed[index] = max(smoothed[index], value)
        f20, f134, f2d = smoothed

    threshold = constants["state_threshold"]
    min_scale = constants["state_min_scale"]
    boost = (((threshold - current) / threshold) * (1.0 - min_scale) +
             min_scale) if current < threshold else min_scale

    groups = {
        "A": (0, 4, adjusted, 1.0, 1.0, 1.0, header[1], boost, 0),
        "B": (4, 8, adjusted, header[3], 1.0, (f20 + f4f) / f34,
              header[3], boost, 1),
        "D": (8, 11, rpm_value, header[4], 1.0, 1.0, header[4], 1.0, 2),
        "F": (11, 14, rpm_value, header[6], header[7], f134 / header[6],
              header[6], 1.0, 3),
        "H": (14, 16, rpm_value, constants["request_amplitude"], 1.0,
              f2d / constants["request_amplitude"],
              constants["request_amplitude"], 1.0, 4),
    }
    result = []
    for layer in layers:
        (first, last, layer_rpm, amplitude, scale_volume, factor,
         ceiling, rpm_scale, slot) = groups[layer["envelope_source"]]
        index = layer["layer"]
        pitch, _ = envelope_output(layer["envelope"], layer_rpm, amplitude,
                                   layer_base[index], scale_volume, header)
        level = pitch * factor
        if layer["envelope_source"] == "A":
            level += f34 + f4f
        if layer["rpm_limit"] and layer_rpm < layer["rpm_limit"]:
            level *= ((layer_rpm / layer["rpm_limit"]) *
                      (1.0 - layer["scale"]) + layer["scale"])
        level = int(level * rpm_scale)
        if layer["envelope_source"] == "B":
            level -= int(float(s.get("sub", 0.0)))
        if layer["envelope_source"] == "D":
            scale = constants["request_pitch"]
            if current < header[11]:
                scale = ((header[11] - current) / header[11]) * \
                    (1.0 - scale) + scale
            level = int(level * scale)
        elif layer["envelope_source"] == "F":
            scale = header[9]
            if current < constants["boost_limit"]:
                scale = ((constants["boost_limit"] - current) /
                         constants["boost_limit"]) * (1.0 - scale) + scale
            level = int(level * scale)
        elif layer["envelope_source"] == "H":
            level = int(level * float(s.get("curve_scale", 1.0)))
        volume = clamp_volume(layer["base"] + base[slot] - ceiling + int(level))
        result.append({
            "layer": index,
            "tone": layer["tone"],
            "source": layer["envelope_source"],
            "pitch": pitch,
            "level": int(level),
            "volume": volume,
        })
    return result


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
        "runtime_constants": layout["runtime_constants"],
        "envelope_layers": {
            str(engine_sound): layer_envelopes(layout, engine_sound)
            for engine_sound in range(layout["counts"]["sounds"])
        },
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
        "%d engine sounds x %d layer envelopes resolved from A/B/D/F/H" %
        (len(data["envelope_layers"]), LAYER_COUNT),
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
