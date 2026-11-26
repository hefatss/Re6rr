"""Pack shipped Enma input-simulation facts into an R6ESIM blob.

    python tools/engine/enma_sim_catalog.py \
        --out build/tmp/enma_sim.r6esim

Facts come from docs/recon/enma_sim.json: six CGameInput getters, three
single-offset probe hits and the 4096-byte default config image. Values are
copied as raw bits; no DLL is loaded or called.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "enma_sim.json")

MAGIC = b"R6ESIM\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
GETTER = struct.Struct("<6I")
HIT = struct.Struct("<2I")
WORD = struct.Struct("<I")
KIND = {"float": 0, "int": 1, "bool": 2}


def bits(value, kind):
    if kind == "float":
        return struct.unpack("<I", struct.pack("<f", value))[0]
    if kind == "int":
        return value & 0xffffffff
    return 1 if value else 0


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    getters = data["getters"]
    config = bytes.fromhex(data["config_default_hex"])
    assert len(getters) == 6 and len(config) == 4096
    assert sum(len(item["hits"]) for item in getters.values()) == 4
    return getters, config


def build(getters, config):
    hit_count = sum(len(item["hits"]) for item in getters.values())
    hit_off = HEADER.size + GETTER.size * len(getters)
    config_off = hit_off + HIT.size * hit_count
    strings_off = config_off + len(config)
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    first_hit = 0
    getter_payload = bytearray()
    hit_payload = bytearray()
    for name, item in getters.items():
        kind_name = type(item["baseline"]).__name__
        kind = KIND[kind_name]
        getter_payload.extend(GETTER.pack(
            add(name), add(item["export"]), first_hit, len(item["hits"]),
            kind, bits(item["baseline"], kind_name)))
        for hit in item["hits"]:
            hit_payload.extend(HIT.pack(hit["offset"],
                                        bits(hit["value"], kind_name)))
        first_hit += len(item["hits"])

    header = HEADER.pack(MAGIC, VERSION, len(getters), hit_count,
                         len(config), len(strings), strings_off)
    return (header + bytes(getter_payload) + bytes(hit_payload) + config +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    getters, config = collect(args.report)
    blob = build(getters, config)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: 6 getters, 4 probe hits, 4096 config bytes, %d bytes" %
          (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
