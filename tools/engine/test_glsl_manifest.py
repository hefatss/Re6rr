"""Check the compiled GLSL binding manifest against the C core reader."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import glsl_manifest  # noqa: E402
import nsxr_shader  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6


class View(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("size", ctypes.c_size_t),
                ("count", ctypes.c_uint32), ("records", ctypes.c_uint32),
                ("cbuffers", ctypes.c_uint32), ("regions", ctypes.c_uint32),
                ("samplers", ctypes.c_uint32), ("strings", ctypes.c_uint32)]


class Record(ctypes.Structure):
    _fields_ = [("flags", ctypes.c_uint32), ("cbuffers", ctypes.c_uint16),
                ("samplers", ctypes.c_uint16),
                ("cbuffer_first", ctypes.c_uint32),
                ("name_off", ctypes.c_uint32)]


class Cbuffer(ctypes.Structure):
    _fields_ = [("binding", ctypes.c_uint32), ("name_off", ctypes.c_uint32),
                ("size", ctypes.c_uint32), ("slots", ctypes.c_uint16),
                ("ubo", ctypes.c_uint16), ("regions", ctypes.c_uint16),
                ("region_first", ctypes.c_uint32)]


class Region(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32), ("size", ctypes.c_uint16),
                ("kind", ctypes.c_uint8), ("type", ctypes.c_uint8)]


class Sampler(ctypes.Structure):
    _fields_ = [("unit", ctypes.c_uint32), ("texture_off", ctypes.c_uint32),
                ("sampler_off", ctypes.c_uint32)]


def configure(lib):
    lib.r6_glsl_bindings_init.restype = ctypes.c_int
    lib.r6_glsl_bindings_init.argtypes = [
        ctypes.POINTER(View), ctypes.c_void_p, ctypes.c_size_t]
    lib.r6_glsl_bindings_get_record.restype = ctypes.c_int
    lib.r6_glsl_bindings_get_record.argtypes = [
        ctypes.POINTER(View), ctypes.c_uint32, ctypes.POINTER(Record)]
    lib.r6_glsl_bindings_get_cbuffer.restype = ctypes.c_int
    lib.r6_glsl_bindings_get_cbuffer.argtypes = [
        ctypes.POINTER(View), ctypes.POINTER(Record), ctypes.c_uint32,
        ctypes.POINTER(Cbuffer)]
    lib.r6_glsl_bindings_region.restype = ctypes.c_int
    lib.r6_glsl_bindings_region.argtypes = [
        ctypes.POINTER(View), ctypes.POINTER(Cbuffer), ctypes.c_uint32,
        ctypes.POINTER(Region)]
    lib.r6_glsl_bindings_get_sampler.restype = ctypes.c_int
    lib.r6_glsl_bindings_get_sampler.argtypes = [
        ctypes.POINTER(View), ctypes.POINTER(Record), ctypes.c_uint32,
        ctypes.POINTER(Sampler)]
    lib.r6_glsl_bindings_name.restype = ctypes.c_char_p
    lib.r6_glsl_bindings_name.argtypes = [ctypes.POINTER(View),
                                          ctypes.c_uint32]


def manifest_entries(name, records):
    entries = []
    for record in records:
        reflection = next(chunk["reflection"] for chunk
                          in record["dxbc"]["chunks"] if chunk["tag"] == "RDEF")
        entries.append({"shader": name, "stage": record["index"],
                        "stage_kind": reflection["stage"],
                        "bindings": nsxr_shader.glsl_bindings(record)})
    return entries


def build_body_manifest(dump):
    path = os.path.join(dump, nsxr_shader.SHADER_DIR, "Body.nsh")
    return {"shaders": manifest_entries(
        "Body.nsh", nsxr_shader.parse_nsh(path)["records"])}


def build_corpus_manifest(dump):
    shaders = nsxr_shader.collect(dump)["shaders"]
    entries = []
    for name, shader in sorted(shaders.items()):
        entries.extend(manifest_entries(name, shader["records"]))
    return {"shaders": entries}


def check(condition, label, failures):
    if not condition:
        failures.append(label)


def check_corpus(lib, manifest, failures):
    blob = glsl_manifest.build(manifest)
    buffer = ctypes.create_string_buffer(blob, len(blob))
    view = View()
    check(lib.r6_glsl_bindings_init(ctypes.byref(view), buffer,
                                    len(blob)) == R6_OK and
          view.count == len(manifest["shaders"]), "corpus init", failures)
    totals = [0, 0, 0]
    for index, entry in enumerate(manifest["shaders"]):
        want = entry["bindings"]
        flags = 0 if want["stage"] == "vertex" else 1
        if want["ubo"]:
            flags |= 0x100
        record = Record()
        rc = lib.r6_glsl_bindings_get_record(ctypes.byref(view), index,
                                             ctypes.byref(record))
        check(rc == R6_OK and record.flags == flags and
              record.cbuffers == len(want["cbuffers"]) and
              record.samplers == len(want["samplers"]),
              "corpus record %d" % index, failures)
        if rc != R6_OK:
            continue
        totals[0] += record.cbuffers
        totals[2] += record.samplers
        for cb_index, block_want in enumerate(want["cbuffers"]):
            block = Cbuffer()
            rc = lib.r6_glsl_bindings_get_cbuffer(
                ctypes.byref(view), ctypes.byref(record), cb_index,
                ctypes.byref(block))
            check(rc == R6_OK and block.binding == block_want["binding"] and
                  block.regions == len(block_want["regions"]),
                  "corpus cbuffer %d/%d" % (index, cb_index), failures)
            if rc != R6_OK:
                continue
            totals[1] += block.regions
            for region_index in range(block.regions):
                region = Region()
                check(lib.r6_glsl_bindings_region(
                    ctypes.byref(view), ctypes.byref(block), region_index,
                    ctypes.byref(region)) == R6_OK,
                    "corpus region %d/%d/%d" % (index, cb_index,
                                                region_index), failures)
        for sampler_index in range(record.samplers):
            sampler = Sampler()
            check(lib.r6_glsl_bindings_get_sampler(
                ctypes.byref(view), ctypes.byref(record), sampler_index,
                ctypes.byref(sampler)) == R6_OK,
                "corpus sampler %d/%d" % (index, sampler_index), failures)
    check(totals == [797, 2029, 526], "corpus totals %s" % totals, failures)
    return len(blob)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--dll", default=os.path.join(
        ROOT, "build", "engine", "r6_engine.dll"))
    args = parser.parse_args()

    failures = []
    manifest = build_body_manifest(args.dump)
    blob = glsl_manifest.build(manifest)
    check(blob == glsl_manifest.build(manifest), "deterministic build",
          failures)
    lib = test_engine.load_core(args.dll, args.dump)
    configure(lib)

    buffer = ctypes.create_string_buffer(blob, len(blob))
    view = View()
    check(lib.r6_glsl_bindings_init(ctypes.byref(view), buffer,
                                    len(blob)) == R6_OK and
          view.count == 2, "manifest init", failures)

    record = Record()
    check(lib.r6_glsl_bindings_get_record(ctypes.byref(view), 1,
                                      ctypes.byref(record)) == R6_OK and
          record.flags == 0x101 and record.cbuffers == 2 and
          record.samplers == 3 and
          lib.r6_glsl_bindings_name(ctypes.byref(view),
                                    record.name_off) == b"Body.nsh",
          "pixel record", failures)

    bindings = manifest["shaders"][1]["bindings"]
    for index, want in enumerate(bindings["cbuffers"]):
        block = Cbuffer()
        check(lib.r6_glsl_bindings_get_cbuffer(ctypes.byref(view),
                                           ctypes.byref(record), index,
                                           ctypes.byref(block)) == R6_OK and
              block.binding == want["binding"] and block.size == want["size"] and
              block.slots == want["slots"] and
              block.ubo == (1 if want["ubo"] else 0) and
              lib.r6_glsl_bindings_name(ctypes.byref(view),
                                        block.name_off) == want["name"].encode(),
              "cbuffer %d" % index, failures)
        for region_index, region in enumerate(want["regions"]):
            got = Region()
            check(lib.r6_glsl_bindings_region(ctypes.byref(view),
                                              ctypes.byref(block),
                                              region_index,
                                              ctypes.byref(got)) == R6_OK and
                  got.offset == region["offset"] and
                  got.size == region["size"] and
                  got.kind == {"scalar": 0, "vector": 1, "matrix": 2}[
                      region["kind"]] and
                  got.type == {"float": 0, "uint": 1}[region["type"]],
                  "region %d/%d" % (index, region_index), failures)
    for index, want in enumerate(bindings["samplers"]):
        sampler = Sampler()
        check(lib.r6_glsl_bindings_get_sampler(ctypes.byref(view),
                                           ctypes.byref(record), index,
                                           ctypes.byref(sampler)) == R6_OK and
              sampler.unit == want["unit"] and
              lib.r6_glsl_bindings_name(ctypes.byref(view),
                                        sampler.texture_off) ==
              want["texture"].encode() and
              lib.r6_glsl_bindings_name(ctypes.byref(view),
                                        sampler.sampler_off) ==
              want["sampler"].encode(),
              "sampler %d" % index, failures)

    short = ctypes.create_string_buffer(blob[:16], 16)
    bad = View()
    check(lib.r6_glsl_bindings_init(ctypes.byref(bad), short, 16) ==
          R6_ERR_ARG, "short manifest", failures)
    corrupt = bytearray(blob)
    corrupt[4] = 2
    bad_buffer = ctypes.create_string_buffer(bytes(corrupt), len(corrupt))
    check(lib.r6_glsl_bindings_init(ctypes.byref(bad), bad_buffer,
                                    len(corrupt)) == R6_ERR_FORMAT,
          "bad version", failures)
    check(lib.r6_glsl_bindings_get_record(ctypes.byref(view), 2,
                                      ctypes.byref(record)) == R6_ERR_ARG,
          "bad record index", failures)
    corpus_bytes = check_corpus(lib, build_corpus_manifest(args.dump),
                                failures)

    if failures:
        for item in failures:
            print("FAIL " + item)
        return 1
    print("GLSL binding manifest: 2 records + 446-record corpus, %d/%d bytes, "
          "797 cbuffers, 2029 regions, 526 samplers, error checks: OK" %
          (len(blob), corpus_bytes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
