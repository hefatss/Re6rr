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

    def signature(record, tag):
        return next(chunk["signature"]
                    for chunk in record["dxbc"]["chunks"]
                    if chunk["tag"] == tag)

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
    signatures = [chunk for record in records
                  for chunk in record["dxbc"]["chunks"]
                  if chunk["tag"] in ("ISGN", "OSGN")]
    assert len(signatures) == 892
    assert all(chunk["signature"]["entries"] for chunk in signatures)

    with tempfile.TemporaryDirectory() as directory:
        output = os.path.join(directory, "body.dxbc")
        record = nsxr_shader.extract(dump, "Body.nsh", 0, output)
        raw = open(output, "rb").read()
        assert len(raw) == record["dxbc_size"] == 0x9a8
        assert raw[:4] == b"DXBC"
    print("  223 .nsh files, 446 DXBC blobs, one extract round-trip: all shader checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
