"""Compile a GLSL export manifest into a fixed-layout binary for the C core.

    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --glsl-dir build/tmp/glsl
    python tools/engine/glsl_manifest.py \
        --manifest build/tmp/glsl/manifest.json \
        --out build/tmp/glsl/bindings.r6glsl

Only data the freestanding host needs is stored: shader/stage flags, UBO
regions, sampler pairs and interned names. GLSL sources stay in the export
directory; no dump data is committed.
"""

import argparse
import json
import struct

MAGIC = b"R6GB"
VERSION = 1

HEADER = struct.Struct("<4sHHIIIIII")
RECORD = struct.Struct("<IHHII")
CBUFFER = struct.Struct("<IIIHHHHI")
REGION = struct.Struct("<IHBB")
SAMPLER = struct.Struct("<III")

STAGE = {"vertex": 0, "pixel": 1}
KIND = {"scalar": 0, "vector": 1, "matrix": 2}
TYPE = {"float": 0, "uint": 1}


def build(manifest):
    """Return deterministic binary bindings for an export_glsl() manifest."""
    entries = manifest["shaders"] if isinstance(manifest, dict) else manifest
    records = bytearray()
    cbuffers = bytearray()
    regions = bytearray()
    samplers = bytearray()
    strings = bytearray(b"\0")
    offsets = {b"": 0}

    def intern(value):
        encoded = value.encode("utf8") + b"\0"
        if encoded not in offsets:
            offsets[encoded] = len(strings)
            strings.extend(encoded)
        return offsets[encoded]

    for entry in entries:
        bindings = entry["bindings"]
        stage = STAGE[bindings["stage"]]
        if bindings["ubo"]:
            stage |= 0x100
        first_buffer = len(cbuffers) // CBUFFER.size
        for block in bindings["cbuffers"]:
            first_region = len(regions) // REGION.size
            cbuffers.extend(CBUFFER.pack(
                block["binding"], intern(block["name"]), block["size"],
                block["slots"], 1 if block["ubo"] else 0,
                len(block["regions"]), 0, first_region))
            for region in block["regions"]:
                regions.extend(REGION.pack(
                    region["offset"], region["size"],
                    KIND[region["kind"]], TYPE[region["type"]]))
        for item in bindings["samplers"]:
            samplers.extend(SAMPLER.pack(
                item["unit"], intern(item["texture"]),
                intern(item["sampler"])))
        records.extend(RECORD.pack(
            stage, len(bindings["cbuffers"]), len(bindings["samplers"]),
            first_buffer, intern(entry["shader"])))

    record_off = HEADER.size
    cbuffer_off = record_off + len(records)
    region_off = cbuffer_off + len(cbuffers)
    sampler_off = region_off + len(regions)
    string_off = sampler_off + len(samplers)
    # Table indices and interned names are relative while building; the core
    # reads absolute buffer offsets, so patch them once table starts are known.
    for position in range(0, len(records), RECORD.size):
        flags, cbuffer_count, sampler_count, first, name = \
            RECORD.unpack_from(records, position)
        RECORD.pack_into(records, position, flags, cbuffer_count,
                         sampler_count,
                         cbuffer_off + first * CBUFFER.size,
                         string_off + name)
    for position in range(0, len(cbuffers), CBUFFER.size):
        fields = list(CBUFFER.unpack_from(cbuffers, position))
        fields[1] += string_off
        fields[7] = region_off + fields[7] * REGION.size
        CBUFFER.pack_into(cbuffers, position, *fields)
    for position in range(0, len(samplers), SAMPLER.size):
        unit, texture, sampler = SAMPLER.unpack_from(samplers, position)
        SAMPLER.pack_into(samplers, position, unit,
                          string_off + texture, string_off + sampler)
    header = HEADER.pack(MAGIC, VERSION, 0, len(entries), record_off,
                         cbuffer_off, region_off, sampler_off, string_off)
    return header + bytes(records + cbuffers + regions + samplers + strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with open(args.manifest, encoding="utf8") as stream:
        manifest = json.load(stream)
    payload = build(manifest)
    with open(args.out, "wb") as stream:
        stream.write(payload)
    print("%d records, %d bytes: %s" %
          (len(manifest["shaders"]), len(payload), args.out))


if __name__ == "__main__":
    main()
