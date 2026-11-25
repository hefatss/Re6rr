"""Self-check for the NSXR/DXBC shader container parser."""

import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nsxr_shader  # noqa: E402


def check(dump):
    body = nsxr_shader.parse_nsh(
        os.path.join(dump, nsxr_shader.SHADER_DIR, "Body.nsh"))
    assert body["size"] == 0x2800
    assert body["record_count"] == 2
    assert [record["offset"] for record in body["records"]] == [0xe0, 0xae0]
    assert [record["dxbc_size"] for record in body["records"]] == \
        [0x9a8, 0x158c]
    expected = ["RDEF", "ISGN", "OSGN", "SHDR", "STAT"]
    for record in body["records"]:
        assert [chunk["tag"] for chunk in record["dxbc"]["chunks"]] == \
            expected

    def chunk(record, tag):
        return next(item for item in record["dxbc"]["chunks"]
                    if item["tag"] == tag)

    def signature(record, tag):
        return chunk(record, tag)["signature"]

    vertex_rdef = chunk(body["records"][0], "RDEF")["reflection"]
    pixel_rdef = chunk(body["records"][1], "RDEF")["reflection"]
    assert vertex_rdef["target_version"] == 0x400
    assert vertex_rdef["stage"] == "vertex"
    assert pixel_rdef["stage"] == "pixel"
    assert vertex_rdef["creator"] == pixel_rdef["creator"] == \
        "Microsoft (R) HLSL Shader Compiler 9.29.952.3111"
    assert [item["name"] for item in vertex_rdef["resources"]] == \
        ["CustomParameter", "PerDraw"]
    assert {item["type"] for item in vertex_rdef["resources"]} == {"cbuffer"}
    assert [item["name"] for item in vertex_rdef["cbuffers"]] == \
        ["PerDraw", "CustomParameter"]
    per_draw = vertex_rdef["cbuffers"][0]
    assert per_draw["size"] == 192
    assert [item["name"] for item in per_draw["variables"]] == \
        ["LocalToWorldMatrix", "LocalToViewMatrix",
         "LocalToProjectionMatrix"]
    assert [item["offset"] for item in per_draw["variables"]] == \
        [0, 64, 128]
    assert all(item["size"] == 64 and
               item["type"]["class"] == "matrix_rows" and
               item["type"]["type"] == "float" and
               item["type"]["rows"] == item["type"]["cols"] == 4
               for item in per_draw["variables"])
    custom = vertex_rdef["cbuffers"][1]
    assert [item["name"] for item in custom["variables"]] == \
        ["cVSEyePos", "cVSFogColorNear", "cVSFogColorFar", "cVSFogParam"]
    assert all(item["size"] == 16 and item["type"]["class"] == "vector" and
               item["type"]["cols"] == 4 for item in custom["variables"])
    alpha = pixel_rdef["cbuffers"][0]
    assert [item["name"] for item in alpha["variables"]] == \
        ["AlphaTestRef", "AlphaTestFunc"]
    assert [item["type"]["type"] for item in alpha["variables"]] == \
        ["float", "uint"]
    assert len(pixel_rdef["resources"]) == 8
    assert [item["type"] for item in pixel_rdef["resources"]].count("sampler") \
        == 3

    vertex_stat = chunk(body["records"][0], "STAT")["statistics"]
    assert [vertex_stat[key] for key in
            ("instruction_count", "temp_register_count", "dcl_count",
             "flt_instruction_count", "static_flow_control_count",
             "mov_instruction_count")] == [37, 2, 12, 18, 1, 5]

    vertex_input = signature(body["records"][0], "ISGN")
    vertex_output = signature(body["records"][0], "OSGN")
    pixel_input = signature(body["records"][1], "ISGN")
    pixel_output = signature(body["records"][1], "OSGN")
    assert [entry["name"] for entry in vertex_input["entries"]] == \
        ["POSITION", "NORMAL", "COLOR", "TEXCOORD"]
    assert [(entry["name"], entry["semantic_index"])
            for entry in vertex_output["entries"]] == \
        [(entry["name"], entry["semantic_index"])
         for entry in pixel_input["entries"]]
    assert {entry["name"] for entry in pixel_output["entries"]} == \
        {"SV_TARGET"}

    data = nsxr_shader.collect(dump)
    shaders = data["shaders"]
    assert len(shaders) == 223
    records = [record for shader in shaders.values()
               for record in shader["records"]]
    assert len(records) == 446
    assert all(record["dxbc"]["size"] == record["dxbc_size"]
               for record in records)
    assert all(len(record["dxbc"]["chunks"]) == 5 for record in records)
    signatures = [item for record in records
                  for item in record["dxbc"]["chunks"]
                  if item["tag"] in ("ISGN", "OSGN")]
    assert len(signatures) == 892
    assert all(item["signature"]["entries"] for item in signatures)
    reflections = [chunk(record, "RDEF")["reflection"]
                   for record in records]
    assert len(reflections) == 446
    assert sum(item["stage"] == "vertex" for item in reflections) == 223
    assert sum(item["stage"] == "pixel" for item in reflections) == 223
    assert all(item["target_version"] == 0x400 for item in reflections)
    assert {item["creator"] for item in reflections} == \
        {"Microsoft (R) HLSL Shader Compiler 9.29.952.3111"}
    assert sum(len(item["cbuffers"]) for item in reflections) == 797
    assert sum(len(cb["variables"]) for item in reflections
               for cb in item["cbuffers"]) == 2029
    assert sum(len(item["resources"]) for item in reflections) == 1849
    stats = [chunk(record, "STAT")["statistics"] for record in records]
    assert len(stats) == 446
    assert all(item["instruction_count"] > 0 for item in stats)

    with tempfile.TemporaryDirectory() as directory:
        output = os.path.join(directory, "body.dxbc")
        record = nsxr_shader.extract(dump, "Body.nsh", 0, output)
        raw = open(output, "rb").read()
        assert len(raw) == record["dxbc_size"] == 0x9a8
        assert raw[:4] == b"DXBC"
    print("  223 .nsh files, 446 DXBC blobs, 446 RDEF/STAT records, one extract round-trip: all shader checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
