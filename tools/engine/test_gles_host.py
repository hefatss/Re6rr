"""Check the freestanding GLES call layer against a ctypes sink."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import glsl_manifest  # noqa: E402
import glsl_ubo  # noqa: E402
import nsxr_shader  # noqa: E402
import test_engine  # noqa: E402
import test_glsl_manifest  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6

SHADER_FN = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
                            ctypes.c_char_p, ctypes.c_size_t)
UNIFORM_FN = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
                             ctypes.c_void_p, ctypes.c_size_t)
TEXTURE_FN = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
                             ctypes.POINTER(test_engine.GlslTextureDesc),
                             ctypes.c_void_p, ctypes.c_size_t)
DRAW_FN = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)

KIND = {"scalar": 0, "vector": 1, "matrix": 2}
TYPE = {"float": 0, "uint": 1}


class Sink(ctypes.Structure):
    _fields_ = [("user", ctypes.c_void_p), ("shader", SHADER_FN),
                ("uniform_block", UNIFORM_FN), ("texture", TEXTURE_FN),
                ("draw", DRAW_FN)]


def configure(lib):
    lib.r6_gles_program_count.restype = ctypes.c_int
    lib.r6_gles_program_count.argtypes = [
        ctypes.POINTER(test_glsl_manifest.View)]
    lib.r6_gles_program.restype = ctypes.c_int
    lib.r6_gles_program.argtypes = [
        ctypes.POINTER(test_glsl_manifest.View), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_gles_emit_program.restype = ctypes.c_int
    lib.r6_gles_emit_program.argtypes = [
        ctypes.POINTER(Sink), ctypes.POINTER(test_glsl_manifest.View),
        ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t,
        ctypes.c_char_p, ctypes.c_size_t]
    lib.r6_gles_emit_shader.restype = ctypes.c_int
    lib.r6_gles_emit_shader.argtypes = [
        ctypes.POINTER(Sink), ctypes.POINTER(test_glsl_manifest.View),
        ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
    lib.r6_gles_emit_uniforms.restype = ctypes.c_int
    lib.r6_gles_emit_uniforms.argtypes = [
        ctypes.POINTER(Sink), ctypes.POINTER(test_glsl_manifest.View),
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
        ctypes.POINTER(test_engine.GlslRegion),
        ctypes.POINTER(test_engine.GlslValue), ctypes.c_uint32]
    lib.r6_gles_emit_texture.restype = ctypes.c_int
    lib.r6_gles_emit_texture.argtypes = [
        ctypes.POINTER(Sink), ctypes.c_uint32, ctypes.c_uint8,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t]
    lib.r6_gles_emit_draw.restype = ctypes.c_int
    lib.r6_gles_emit_draw.argtypes = [ctypes.POINTER(Sink), ctypes.c_uint32]


class Recorder:
    def __init__(self):
        self.calls = []
        self.draw_result = 0
        self.shader = SHADER_FN(self.on_shader)
        self.uniform = UNIFORM_FN(self.on_uniform)
        self.texture = TEXTURE_FN(self.on_texture)
        self.draw = DRAW_FN(self.on_draw)
        self.sink = Sink(None, self.shader, self.uniform, self.texture,
                         self.draw)

    def on_shader(self, user, stage, source, size):
        self.calls.append(("shader", stage, source[:size]))
        return R6_OK

    def on_uniform(self, user, binding, data, size):
        self.calls.append(("uniform", binding, ctypes.string_at(data, size)))
        return R6_OK

    def on_texture(self, user, unit, desc, pixels, size):
        self.calls.append(("texture", unit,
                           tuple(getattr(desc.contents, field) for field in
                                 ("unit", "internal_format", "format",
                                  "type", "width", "height", "size")),
                           ctypes.string_at(pixels, size)))
        return R6_OK

    def on_draw(self, user, count):
        self.calls.append(("draw", count))
        return self.draw_result


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    manifest = test_glsl_manifest.build_body_manifest(dump)
    blob = glsl_manifest.build(manifest)
    buffer = ctypes.create_string_buffer(blob, len(blob))
    view = test_glsl_manifest.View()
    assert lib.r6_glsl_bindings_init(ctypes.byref(view), buffer,
                                     len(blob)) == R6_OK
    test_glsl_manifest.configure(lib)

    path = os.path.join(dump, nsxr_shader.SHADER_DIR, "Body.nsh")
    records = nsxr_shader.parse_nsh(path)["records"]
    source = nsxr_shader.glsl_es_source(records[1]).encode("utf8")

    recorder = Recorder()
    assert lib.r6_gles_emit_shader(ctypes.byref(recorder.sink),
                                   ctypes.byref(view), 1, source,
                                   len(source)) == R6_OK
    assert recorder.calls[-1] == ("shader", 1, source)
    assert lib.r6_gles_emit_shader(ctypes.byref(recorder.sink),
                                   ctypes.byref(view), 0, source,
                                   len(source)) == R6_OK
    assert recorder.calls[-1][1] == 0

    assert lib.r6_gles_program_count(ctypes.byref(view)) == 1
    vertex_index = ctypes.c_uint32()
    pixel_index = ctypes.c_uint32()
    assert lib.r6_gles_program(ctypes.byref(view), 0,
                               ctypes.byref(vertex_index),
                               ctypes.byref(pixel_index)) == R6_OK
    assert (vertex_index.value, pixel_index.value) == (0, 1)
    vertex_source = nsxr_shader.glsl_es_source(records[0]).encode("utf8")
    assert lib.r6_gles_emit_program(
        ctypes.byref(recorder.sink), ctypes.byref(view), 0,
        vertex_source, len(vertex_source), source, len(source)) == R6_OK
    assert recorder.calls[-2:] == [("shader", 0, vertex_source),
                                   ("shader", 1, source)]
    assert lib.r6_gles_emit_program(
        ctypes.byref(recorder.sink), ctypes.byref(view), 1,
        vertex_source, len(vertex_source), source, len(source)) == R6_ERR_ARG
    assert lib.r6_gles_emit_program(
        ctypes.byref(recorder.sink), ctypes.byref(view), 0,
        vertex_source, len(vertex_source), b"bad", 3) == R6_ERR_ARG

    bindings = manifest["shaders"][1]["bindings"]
    block = bindings["cbuffers"][0]
    regions = (test_engine.GlslRegion * len(block["regions"]))()
    values = (test_engine.GlslValue * len(block["regions"]))()
    named = {}
    for index, region in enumerate(block["regions"]):
        regions[index].offset = region["offset"]
        regions[index].size = region["size"]
        regions[index].kind = KIND[region["kind"]]
        regions[index].type = TYPE[region["type"]]
        value = [index + 1 + part for part in range(
            1 if region["kind"] == "scalar" else
            4 if region["kind"] == "vector" else 16)]
        if region["kind"] == "scalar":
            if regions[index].type == 1:
                values[index].u = value[0]
            else:
                values[index].f = value[0]
        elif region["kind"] == "vector":
            values[index].v = (ctypes.c_float * 4)(*value)
        else:
            values[index].m = (ctypes.c_float * 16)(*value)
        named[region["name"]] = value
    expected = glsl_ubo.pack_ubo(bindings, block["name"], named)
    scratch = ctypes.create_string_buffer(block["size"])
    rc = lib.r6_gles_emit_uniforms(
        ctypes.byref(recorder.sink), ctypes.byref(view), 1, 0, scratch,
        block["size"], regions, values, len(regions))
    assert rc == R6_OK
    assert recorder.calls[-1] == ("uniform", block["binding"], expected)

    pixels = bytes(range(64))
    assert lib.r6_gles_emit_texture(ctypes.byref(recorder.sink), 6, 0x0e,
                                    4, 4, pixels, len(pixels)) == R6_OK
    unit, desc, raw = recorder.calls[-1][1:]
    assert unit == 6 and raw == pixels
    assert dict(zip(("unit", "internal_format", "format", "type", "width",
                     "height", "size"), desc)) == \
        glsl_ubo.texture_upload(6, 0x0e, 4, 4)

    assert lib.r6_gles_emit_draw(ctypes.byref(recorder.sink), 36) == R6_OK
    assert recorder.calls[-1] == ("draw", 36)
    recorder.draw_result = -7
    assert lib.r6_gles_emit_draw(ctypes.byref(recorder.sink), 36) == -7

    empty = Sink()
    empty.shader = ctypes.cast(ctypes.c_void_p(), SHADER_FN)
    empty.uniform = recorder.uniform
    empty.texture = recorder.texture
    empty.draw = recorder.draw
    assert lib.r6_gles_emit_shader(ctypes.byref(empty), ctypes.byref(view), 1,
                                   source, len(source)) == R6_ERR_ARG
    bad_source = b"void main() {}"
    assert lib.r6_gles_emit_shader(ctypes.byref(recorder.sink),
                                   ctypes.byref(view), 1, bad_source,
                                   len(bad_source)) == R6_ERR_ARG
    assert lib.r6_gles_emit_shader(ctypes.byref(recorder.sink),
                                   ctypes.byref(view), 99, source,
                                   len(source)) == R6_ERR_ARG
    assert lib.r6_gles_emit_uniforms(
        ctypes.byref(recorder.sink), ctypes.byref(view), 1, 0, scratch,
        block["size"], regions, values, len(regions) - 1) == R6_ERR_ARG
    shifted = test_engine.GlslRegion(*(regions[0].offset + 4,
                                       regions[0].size, regions[0].kind,
                                       regions[0].type))
    altered = (test_engine.GlslRegion * len(regions))()
    for index in range(len(regions)):
        altered[index] = regions[index]
    altered[0] = shifted
    assert lib.r6_gles_emit_uniforms(
        ctypes.byref(recorder.sink), ctypes.byref(view), 1, 0, scratch,
        block["size"], altered, values, len(regions)) == R6_ERR_FORMAT
    assert lib.r6_gles_emit_texture(ctypes.byref(recorder.sink), 6, 0x55,
                                    4, 4, pixels, len(pixels)) == R6_ERR_FORMAT
    assert lib.r6_gles_emit_texture(ctypes.byref(recorder.sink), 6, 0x0e,
                                    4, 4, pixels, len(pixels) - 1) == \
        R6_ERR_BUFFER

    corpus = glsl_manifest.build(test_glsl_manifest.build_corpus_manifest(dump))
    corpus_buffer = ctypes.create_string_buffer(corpus, len(corpus))
    corpus_view = test_glsl_manifest.View()
    assert lib.r6_glsl_bindings_init(ctypes.byref(corpus_view), corpus_buffer,
                                     len(corpus)) == R6_OK
    assert lib.r6_gles_program_count(ctypes.byref(corpus_view)) == 223
    used = set()
    for index in range(223):
        assert lib.r6_gles_program(ctypes.byref(corpus_view), index,
                                   ctypes.byref(vertex_index),
                                   ctypes.byref(pixel_index)) == R6_OK
        vertex = test_glsl_manifest.Record()
        pixel = test_glsl_manifest.Record()
        assert lib.r6_glsl_bindings_get_record(
            ctypes.byref(corpus_view), vertex_index.value,
            ctypes.byref(vertex)) == R6_OK
        assert lib.r6_glsl_bindings_get_record(
            ctypes.byref(corpus_view), pixel_index.value,
            ctypes.byref(pixel)) == R6_OK
        assert not (vertex.flags & 1) and pixel.flags & 1
        assert lib.r6_glsl_bindings_name(
            ctypes.byref(corpus_view), vertex.name_off) == \
            lib.r6_glsl_bindings_name(ctypes.byref(corpus_view),
                                      pixel.name_off)
        used.update((vertex_index.value, pixel_index.value))
    assert len(used) == 446
    print("GLES host layer: 223 programs, 2 stages, %d-byte UBO, RGBA8 upload "
          "and draw forwarded; sink/null/index/format errors: OK" %
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
