"""Self-check for the NSXR/DXBC shader container parser."""

import argparse
import os
import re
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

    vertex_code = chunk(body["records"][0], "SHDR")["code"]
    pixel_code = chunk(body["records"][1], "SHDR")["code"]
    assert vertex_code["version"] == pixel_code["version"] == 0x40
    assert vertex_code["shader_type"] == "vertex"
    assert pixel_code["shader_type"] == "pixel"
    assert [vertex_code["instruction_count"],
            pixel_code["instruction_count"]] == [37, 153]
    assert [vertex_code["declaration_count"],
            pixel_code["declaration_count"]] == [15, 18]
    assert vertex_code["opcodes"]["MAD"] == 13
    assert "SAMPLE" not in vertex_code["opcodes"]
    assert pixel_code["opcodes"]["SAMPLE"] == 3
    assert pixel_code["opcodes"]["DCL_SAMPLER"] == 3
    assert pixel_code["opcodes"]["DCL_RESOURCE"] == 3
    assert pixel_code["opcodes"]["DISCARD"] == 14
    assert pixel_code["opcodes"]["DCL_OUTPUT"] == 3

    body_flow = nsxr_shader.control_flow(pixel_code["instructions"])
    assert [block["kind"] for block in body_flow["blocks"]] == \
        ["switch", "switch"]
    assert not body_flow["unmatched"]
    switch = body_flow["blocks"][0]
    assert switch["start"] < switch["cases"][0]["start"] < switch["end"]
    assert len(switch["breaks"]) == 9

    depth = nsxr_shader.parse_nsh(
        os.path.join(dump, nsxr_shader.SHADER_DIR, "DepthBlend.nsh"))
    depth_code = next(chunk["code"] for chunk
                      in depth["records"][1]["dxbc"]["chunks"]
                      if chunk["tag"] == "SHDR")
    depth_flow = nsxr_shader.control_flow(depth_code["instructions"])
    assert [block["kind"] for block in depth_flow["blocks"]] == \
        ["if", "loop", "loop"]
    assert not depth_flow["unmatched"]
    assert depth_flow["blocks"][1]["continues"] == [31]

    vertex_uniforms = nsxr_shader.uniform_usage(body["records"][0])
    pixel_uniforms = nsxr_shader.uniform_usage(body["records"][1])
    assert vertex_uniforms["dynamic"] == pixel_uniforms["dynamic"] == 0
    assert vertex_uniforms["usage"]["PerDraw.LocalToWorldMatrix"] > 0
    assert vertex_uniforms["usage"]["PerDraw.LocalToProjectionMatrix"] > 0
    assert "PerDraw.LocalToViewMatrix" not in vertex_uniforms["usage"]
    assert vertex_uniforms["usage"]["CustomParameter.cVSEyePos"] == 1
    assert pixel_uniforms["usage"]["AlphaTest.AlphaTestRef"] > 0
    assert pixel_uniforms["usage"]["AlphaTest.AlphaTestFunc"] > 0
    assert not any(name.endswith(".?") for name in
                   vertex_uniforms["usage"].keys() |
                   pixel_uniforms["usage"].keys())

    vertex_resources = nsxr_shader.resource_usage(body["records"][0])
    pixel_resources = nsxr_shader.resource_usage(body["records"][1])
    assert vertex_resources["usage"] == {} and \
        vertex_resources["declared"] == []
    assert pixel_resources["usage"] == {
        "resource:texture00": 1, "resource:texture01": 1,
        "resource:custom_texture06": 1, "sampler:sampler00": 1,
        "sampler:sampler01": 1, "sampler:custom_sampler06": 1}
    assert len(pixel_resources["declared"]) == 6 and \
        pixel_resources["dynamic"] == pixel_resources["unmapped"] == 0

    first_mul = next(item for item in vertex_code["instructions"]
                     if item["name"] == "MUL")
    assert first_mul["offset"] == 196 and first_mul["consumed"] == 8
    assert [op["type"] for op in first_mul["operands"]] == \
        ["temp", "input", "constant_buffer"]
    assert [op["components"] for op in first_mul["operands"]] == \
        ["xyzw", "yyyy", "xyzw"]
    assert first_mul["operands"][2]["indices"] == [
        {"kind": "immediate32", "value": 1},
        {"kind": "immediate32", "value": 9},
    ]
    first_sample = next(item for item in pixel_code["instructions"]
                        if item["name"] == "SAMPLE")
    assert [op["type"] for op in first_sample["operands"]] == \
        ["temp", "input", "resource", "sampler"]
    assert first_sample["operands"][2]["indices"] == \
        [{"kind": "immediate32", "value": 0}]
    assert first_sample["operands"][3]["indices"] == \
        [{"kind": "immediate32", "value": 0}]
    assert all(item["consumed"] == item["length"]
               for item in vertex_code["instructions"] + pixel_code["instructions"])

    vertex_decl = vertex_code["declarations"][0]
    assert vertex_decl["name"] == "DCL_CONSTANT_BUFFER"
    assert vertex_decl["access_pattern"] == 1
    assert vertex_decl["operands"][0]["indices"] == [
        {"kind": "immediate32", "value": 1},
        {"kind": "immediate32", "value": 12},
    ]

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
    usage = [nsxr_shader.uniform_usage(record) for record in records]
    assert sum(item["dynamic"] for item in usage) == 8
    assert not any(name.endswith(".?") for item in usage
                   for name in item["usage"])
    resources = [nsxr_shader.resource_usage(record) for record in records]
    assert sum(sum(item["usage"].values()) for item in resources) == 1360
    assert sum(len(item["declared"]) for item in resources) == 1052
    assert all(item["dynamic"] == item["unmapped"] == 0
               for item in resources)
    assert not any("?" in name for item in resources
                   for name in item["declared"])
    coverage = nsxr_shader.glsl_coverage(data)
    assert coverage["total"] == 20563 and not coverage["unknown"]
    assert {kind: coverage["counts"][kind] for kind in
            ("direct", "lower", "control", "texture")} == {
        "direct": 11184, "lower": 2720, "control": 5979, "texture": 680}
    assert len(nsxr_shader.SM4_GLSL_ES) == 43 and all(
        item["class"] in ("direct", "lower", "control", "texture")
        for item in nsxr_shader.SM4_GLSL_ES.values())
    emitted = 0
    for record in records:
        code = next(chunk["code"] for chunk in record["dxbc"]["chunks"]
                    if chunk["tag"] == "SHDR")
        used = {item["name"] for item in code["instructions"]}
        if used <= nsxr_shader.GLSL_EMIT_OPS:
            source = nsxr_shader.glsl_es_source(record)
            assert source.startswith("#version 300 es") and \
                "void main()" in source and source.count("{") == \
                source.count("}")
            declared_int = set(re.findall(r"ivec4 (ri\d+);", source))
            used_int = set(re.findall(r"\b(ri\d+)\b", source))
            declared_array = set(re.findall(r"vec4 (x\d+)\[", source))
            used_array = set(re.findall(r"\b(x\d+)\[", source))
            assert not used_int - declared_int and \
                not used_array - declared_array and \
                "None" not in source
            emitted += 1
    assert emitted == 404
    copy_source = nsxr_shader.glsl_es_source(shaders["Copy.nsh"]["records"][1])
    assert "uniform sampler2D texture00;" in copy_source and \
        "texture(texture00, vec2(in1.xyxx))" in copy_source and \
        "layout(location=0) out vec4 out0;" in copy_source
    fade_source = nsxr_shader.glsl_es_source(shaders["Fade.nsh"]["records"][1])
    assert "out0 = vec4(in1.xyzw);" in fade_source
    body_source = nsxr_shader.glsl_es_source(shaders["Body.nsh"]["records"][1])
    assert "switch (int(cb13[0].y)) {" in body_source and \
        "case 0:" in body_source and "break;" in body_source and \
        "ivec4 ri0;" in body_source
    star_source = nsxr_shader.glsl_es_source(
        shaders["StarPass00.nsh"]["records"][1])
    assert "for (;;) {" in star_source and \
        "cb0[int(ri0.w)]" in star_source and \
        "cb0[(4 + int(ri0.w))]" in star_source
    env_source = nsxr_shader.glsl_es_source(
        shaders["MapEnvFilter.nsh"]["records"][1])
    assert "vec4 x0[25];" in env_source and \
        "x0[int(ri2.w)].xy" in env_source and \
        "intBitsToFloat(ri2.w)" in env_source
    try:
        nsxr_shader.glsl_es_source(shaders["MapLamp.nsh"]["records"][0])
        raise AssertionError("MapLamp MOVC emitted without semantics")
    except ValueError as error:
        assert "unsupported GLES opcodes: MOVC" in str(error)
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
    code = [chunk(record, "SHDR")["code"] for record in records]
    assert len(code) == 446
    assert all(item["version"] == 0x40 for item in code)
    assert sum(item["instruction_count"] for item in code) == 20563
    assert sum(item["instruction_count"] for item, stat in
               zip(code, stats)) == sum(
                   item["instruction_count"] for item in stats)
    assert sum(item["declaration_count"] for item in code) == 5195
    assert sum(len(instruction["operands"]) for shader in code
               for instruction in shader["instructions"]) == 43827
    assert sum(item["shader_type"] == "vertex" for item in code) == 223
    assert sum(item["shader_type"] == "pixel" for item in code) == 223
    assert all(not any(name.startswith("OP_") for name in item["opcodes"])
               for item in code)
    assert all(item["consumed"] == item["length"]
               for shader in code for item in shader["instructions"])
    assert sum("modifier" in operand for shader in code
               for item in shader["instructions"]
               for operand in item["operands"]) == 1029
    assert sum(item["flags"]["nonzero"] for shader in code
               for item in shader["instructions"]) == 1935

    with tempfile.TemporaryDirectory() as directory:
        output = os.path.join(directory, "body.dxbc")
        record = nsxr_shader.extract(dump, "Body.nsh", 0, output)
        raw = open(output, "rb").read()
        assert len(raw) == record["dxbc_size"] == 0x9a8
        assert raw[:4] == b"DXBC"
    print("  223 .nsh files, 446 DXBC blobs, 20563 instructions, "
          "43827 decoded operands, one extract round-trip: "
          "all shader checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
