"""Check the compiled vertex layout against the C reader."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nsxr_shader  # noqa: E402
import test_engine  # noqa: E402
import test_glsl_manifest  # noqa: E402
import vertex_layout  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_NOT_FOUND = -7


class View(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("size", ctypes.c_size_t),
                ("count", ctypes.c_uint32), ("strings", ctypes.c_uint32)]


class Attrib(ctypes.Structure):
    _fields_ = [("shader_off", ctypes.c_uint32),
                ("location", ctypes.c_uint16),
                ("semantic_index", ctypes.c_uint16),
                ("mask", ctypes.c_uint16),
                ("semantic_off", ctypes.c_uint32)]


def configure(lib):
    lib.r6_vertex_init.restype = ctypes.c_int
    lib.r6_vertex_init.argtypes = [ctypes.POINTER(View), ctypes.c_void_p,
                                   ctypes.c_size_t]
    lib.r6_vertex_get_attrib.restype = ctypes.c_int
    lib.r6_vertex_get_attrib.argtypes = [ctypes.POINTER(View), ctypes.c_uint32,
                                     ctypes.POINTER(Attrib)]
    lib.r6_vertex_find.restype = ctypes.c_int
    lib.r6_vertex_find.argtypes = [ctypes.POINTER(View), ctypes.c_char_p,
                                   ctypes.c_uint16, ctypes.POINTER(Attrib)]
    lib.r6_vertex_name.restype = ctypes.c_char_p
    lib.r6_vertex_name.argtypes = [ctypes.POINTER(View), ctypes.c_uint32]


def expected_records(manifest):
    out = []
    for entry in manifest["shaders"]:
        if entry["bindings"]["stage"] != "vertex":
            continue
        for item in entry["bindings"]["inputs"]:
            out.append((entry["shader"], item["register"],
                        item["semantic_index"], item["mask"],
                        item["semantic"]))
    return out


def check(dump):
    manifest = test_glsl_manifest.build_corpus_manifest(dump)
    expected = expected_records(manifest)
    blob = vertex_layout.build(manifest)
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    buffer = ctypes.create_string_buffer(blob, len(blob))
    view = View()
    assert lib.r6_vertex_init(ctypes.byref(view), buffer, len(blob)) == R6_OK
    assert view.count == len(expected)

    for index, want in enumerate(expected):
        got = Attrib()
        assert lib.r6_vertex_get_attrib(ctypes.byref(view), index,
                                    ctypes.byref(got)) == R6_OK
        assert (got.location, got.semantic_index, got.mask) == want[1:4]
        assert lib.r6_vertex_name(ctypes.byref(view), got.shader_off) == \
            want[0].encode("utf8")
        assert lib.r6_vertex_name(ctypes.byref(view), got.semantic_off) == \
            want[4].encode("utf8")
        found = Attrib()
        assert lib.r6_vertex_find(ctypes.byref(view),
                                  want[0].encode("utf8"), want[1],
                                  ctypes.byref(found)) == R6_OK
        assert ctypes.string_at(ctypes.byref(found),
                                ctypes.sizeof(found)) == \
            ctypes.string_at(ctypes.byref(got), ctypes.sizeof(got))

    record = nsxr_shader.parse_nsh(
        os.path.join(dump, nsxr_shader.SHADER_DIR, "Body.nsh"))["records"]
    source = nsxr_shader.glsl_es_source(record[0])
    for shader, location, _index, _mask, semantic in expected:
        if shader == "Body.nsh":
            assert "layout(location=%d) in vec4 in%d; // %s" % (
                location, location, semantic) in source

    bad = bytearray(blob)
    bad[0] = 0
    assert lib.r6_vertex_init(ctypes.byref(View()),
                              ctypes.create_string_buffer(bytes(bad),
                                                          len(bad)),
                              len(bad)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[4] = 2
    assert lib.r6_vertex_init(ctypes.byref(View()),
                              ctypes.create_string_buffer(bytes(bad),
                                                          len(bad)),
                              len(bad)) == R6_ERR_FORMAT
    assert lib.r6_vertex_init(ctypes.byref(View()), buffer,
                              len(blob) - 1) == R6_ERR_FORMAT
    assert lib.r6_vertex_get_attrib(ctypes.byref(view), view.count,
                                ctypes.byref(Attrib())) == R6_ERR_ARG
    assert lib.r6_vertex_find(ctypes.byref(view), b"NoSuch.nsh", 0,
                              ctypes.byref(Attrib())) == R6_ERR_NOT_FOUND
    print("vertex layout: %d attributes, names/locations/masks and lookups "
          "match GLSL; bad magic/version/truncation/index: OK" %
          len(expected))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
