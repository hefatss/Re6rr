"""Pack EMTIS runtime constants and lexical fields for the C layer evaluator.

    python tools/engine/engine_runtime_catalog.py \
        --dump D:\\Games\\W6W-05 --out build\\tmp\\engine_runtime.r6ers

The blob holds the first 14 EMTIS header values, 20 runtime constants and the
two lexical fields (indices 8 and 13) of every 0xbc-byte sound record. Layer
envelopes remain in `engine_sound.r6esnd`; the evaluator reads both blobs.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_tables  # noqa: E402
import engine_sound  # noqa: E402
import nub_audio  # noqa: E402

MAGIC = b"R6ERS\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIII")
SOUND = struct.Struct("<HHdd")
HEADER_COUNT = 14
CONSTANT_NAMES = (
    "request_amplitude", "request_pitch", "state_threshold",
    "state_min_scale", "pitch_divisor", "rpm_scale", "rpm_base",
    "rpm_step", "envelope_count", "request_count", "curve_count",
    "curve_kind", "boost_limit", "boost_rate", "boost_decay_ms",
    "boost_decay_rate", "boost_count", "boost_time", "boost_rise",
    "boost_fall",
)


def collect(dump):
    emtis = audio_tables.parse_emtis(os.path.join(
        dump, nub_audio.SOUND_DIR, "emtis.tbl"))
    return engine_sound.parse_layout(emtis)


def build(layout):
    constants = layout["runtime_constants"]
    header_values = [float(value) for value in layout["header"][:HEADER_COUNT]]
    constant_values = [float(constants[name]) for name in CONSTANT_NAMES]
    if len(header_values) != HEADER_COUNT:
        raise ValueError("short emtis header")

    sounds = bytearray()
    for index, record in enumerate(layout["sound_records"]):
        sounds.extend(SOUND.pack(index, 0, float(record[8]),
                                 float(record[13])))
    values = bytearray()
    for value in header_values + constant_values:
        values.extend(struct.pack("<d", value))

    return HEADER.pack(MAGIC, VERSION, len(layout["sound_records"]),
                       HEADER_COUNT, len(CONSTANT_NAMES), 0, 0) + \
        bytes(sounds) + bytes(values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    blob = build(collect(args.dump))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d sounds, %d bytes" %
          (args.out, HEADER.unpack_from(blob)[2], len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
