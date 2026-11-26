"""Check the packed engine-sound table against the C core reader."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import engine_sound  # noqa: E402
import engine_sound_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_NOT_FOUND = -7


class EsndHeader(ctypes.Structure):
    _fields_ = [("mapping_count", ctypes.c_uint32),
                ("sound_count", ctypes.c_uint32),
                ("tunes_per_car", ctypes.c_uint32),
                ("layer_count", ctypes.c_uint32)]


class EsndMapping(ctypes.Structure):
    _fields_ = [("car_type", ctypes.c_uint8), ("tune", ctypes.c_uint8),
                ("group", ctypes.c_uint8), ("reserved", ctypes.c_uint8),
                ("engine_sound", ctypes.c_uint16),
                ("reserved16", ctypes.c_uint16),
                ("tones", ctypes.c_int32 * 16)]


class EsndLayer(ctypes.Structure):
    _fields_ = [("layer", ctypes.c_uint8), ("source", ctypes.c_uint8),
                ("flags", ctypes.c_uint8), ("reserved", ctypes.c_uint8),
                ("index", ctypes.c_uint16), ("reserved16", ctypes.c_uint16),
                ("tone", ctypes.c_int32),
                ("envelope", ctypes.c_int32 * 5),
                ("rpm_limit", ctypes.c_int32), ("scale", ctypes.c_float),
                ("base", ctypes.c_int32), ("reserved32", ctypes.c_uint32)]


def configure(lib):
    lib.r6_esnd_parse.restype = ctypes.c_int
    lib.r6_esnd_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(EsndHeader)]
    lib.r6_esnd_find.restype = ctypes.c_int
    lib.r6_esnd_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.c_uint8, ctypes.c_uint8,
                                 ctypes.POINTER(EsndMapping)]
    lib.r6_esnd_get_layer.restype = ctypes.c_int
    lib.r6_esnd_get_layer.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.c_uint16, ctypes.c_uint32,
                                  ctypes.POINTER(EsndLayer)]


def check(dump):
    blob = engine_sound_catalog.build(dump)
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    buffer = ctypes.create_string_buffer(blob, len(blob))
    header = EsndHeader()
    assert lib.r6_esnd_parse(buffer, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.mapping_count, header.sound_count, header.tunes_per_car,
            header.layer_count) == (320, 224, 10, 3584)

    data = engine_sound.collect(dump)
    for want in data["mappings"]:
        got = EsndMapping()
        rc = lib.r6_esnd_find(buffer, len(blob), want["car_type"],
                              want["tune"], ctypes.byref(got))
        assert rc == R6_OK, (want["car_type"], want["tune"], rc)
        assert (got.car_type, got.tune, got.group, got.engine_sound) == \
            (want["car_type"], want["tune"], want["group"],
             want["engine_sound"])
        assert list(got.tones) == want["layer_tones"]

    layers_checked = 0
    for sound in range(data["counts"]["sounds"]):
        for index, want in enumerate(data["envelope_layers"][str(sound)]):
            got = EsndLayer()
            rc = lib.r6_esnd_get_layer(buffer, len(blob), sound, index,
                                   ctypes.byref(got))
            assert rc == R6_OK, (sound, index, rc)
            flags = (1 if want["rpm_limit"] is not None else 0) | \
                    (2 if want["scale"] is not None else 0)
            assert (got.layer, got.index, got.tone) == \
                (want["layer"], want["envelope_index"], want["tone"]), \
                (sound, index)
            assert got.source == engine_sound_catalog.SOURCES[
                want["envelope_source"]], (sound, index)
            assert got.flags == flags, (sound, index)
            assert list(got.envelope) == want["envelope"], (sound, index)
            assert got.rpm_limit == (want["rpm_limit"] or 0), (sound, index)
            assert abs(got.scale - (want["scale"] or 0.0)) < 1e-6, \
                (sound, index)
            assert got.base == want["base"], (sound, index)
            layers_checked += 1

    bad = bytearray(blob)
    bad[0] = 0
    assert lib.r6_esnd_parse(ctypes.create_string_buffer(bytes(bad), len(bad)),
                             len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_esnd_parse(buffer, len(blob) - 1,
                             ctypes.byref(header)) == R6_ERR_FORMAT
    got = EsndMapping()
    assert lib.r6_esnd_find(buffer, len(blob), 200, 200,
                            ctypes.byref(got)) == R6_ERR_NOT_FOUND
    layer = EsndLayer()
    assert lib.r6_esnd_get_layer(buffer, len(blob), 224, 0,
                             ctypes.byref(layer)) == R6_ERR_ARG
    assert lib.r6_esnd_get_layer(buffer, len(blob), 0, 16,
                             ctypes.byref(layer)) == R6_ERR_ARG
    print("engine sound blob: %d mappings, %d layers, %d bytes; "
          "bad magic/truncation/indices: OK" %
          (len(data["mappings"]), layers_checked, len(blob)))


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
