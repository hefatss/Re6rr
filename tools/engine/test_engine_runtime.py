"""Check full 16-layer engine evaluation against the Python reference."""

import ctypes
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import engine_runtime_catalog  # noqa: E402
import engine_sound  # noqa: E402
import engine_sound_catalog  # noqa: E402
import test_engine  # noqa: E402
import test_envelope_runtime  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class RuntimeView(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("size", ctypes.c_size_t),
                ("sound_count", ctypes.c_uint32),
                ("header_count", ctypes.c_uint32),
                ("constant_count", ctypes.c_uint32),
                ("sounds_off", ctypes.c_uint32),
                ("header_off", ctypes.c_uint32),
                ("constants_off", ctypes.c_uint32)]


class State(ctypes.Structure):
    _fields_ = [("rpm", ctypes.c_int32), ("current", ctypes.c_int32),
                ("request_offset", ctypes.c_int32),
                ("base", ctypes.c_double * 5),
                ("layer_base", ctypes.c_double * 16),
                ("flag", ctypes.c_uint32), ("throttle", ctypes.c_double),
                ("floors", (ctypes.c_double * 3) * 3),
                ("smooth34", ctypes.c_double),
                ("smooth4f", ctypes.c_double),
                ("smooth20", ctypes.c_double), ("f134", ctypes.c_double),
                ("f2d", ctypes.c_double), ("sub", ctypes.c_double),
                ("curve_scale", ctypes.c_double)]


class LayerResult(ctypes.Structure):
    _fields_ = [("layer", ctypes.c_uint32), ("source", ctypes.c_uint32),
                ("tone", ctypes.c_int32), ("pitch", ctypes.c_int32),
                ("level", ctypes.c_int32), ("volume", ctypes.c_double)]


def configure(lib):
    lib.r6_engine_runtime_init.restype = ctypes.c_int
    lib.r6_engine_runtime_init.argtypes = [
        ctypes.POINTER(RuntimeView), ctypes.c_void_p, ctypes.c_size_t]
    lib.r6_engine_runtime_sound.restype = ctypes.c_int
    lib.r6_engine_runtime_sound.argtypes = [
        ctypes.POINTER(RuntimeView), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    lib.r6_engine_runtime_header.restype = ctypes.c_int
    lib.r6_engine_runtime_header.argtypes = [
        ctypes.POINTER(RuntimeView), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_double)]
    lib.r6_engine_runtime_constant.restype = ctypes.c_int
    lib.r6_engine_runtime_constant.argtypes = [
        ctypes.POINTER(RuntimeView), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_double)]
    lib.r6_engine_state_init.restype = ctypes.c_int
    lib.r6_engine_state_init.argtypes = [ctypes.POINTER(State),
                                         ctypes.c_int32]
    lib.r6_engine_eval_layers.restype = ctypes.c_int
    lib.r6_engine_eval_layers.argtypes = [
        ctypes.POINTER(RuntimeView), ctypes.c_void_p, ctypes.c_size_t,
        ctypes.c_uint32, ctypes.POINTER(State),
        ctypes.POINTER(test_envelope_runtime.Math),
        ctypes.POINTER(LayerResult), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32)]


def state_values(current, variant):
    return {
        "rpm": current,
        "base": [0.25 * (index + 1) for index in range(5)],
        "layer_base": [1.0 + 0.01 * index for index in range(16)],
        "flag": bool(variant & 1),
        "throttle": 0.25,
        "floors": [(1.0 + variant, 2.0, 0.5),
                   (2.0, 3.0 + variant, 1.0),
                   (3.0, 4.0, 1.5 + variant)],
        "smooth34": 0.2,
        "smooth4f": 0.3,
        "smooth20": 0.4,
        "f134": 0.5,
        "f2d": 0.6,
        "sub": 7.0,
        "curve_scale": 1.1,
    }


def check(dump):
    data = engine_sound.collect(dump)
    layout = engine_runtime_catalog.collect(dump)
    runtime_blob = engine_runtime_catalog.build(layout)
    esnd_blob = engine_sound_catalog.build(dump)
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)

    runtime_buffer = ctypes.create_string_buffer(runtime_blob,
                                                 len(runtime_blob))
    esnd_buffer = ctypes.create_string_buffer(esnd_blob, len(esnd_blob))
    view = RuntimeView()
    assert lib.r6_engine_runtime_init(ctypes.byref(view), runtime_buffer,
                                      len(runtime_blob)) == R6_OK
    assert (view.sound_count, view.header_count, view.constant_count) == \
        (224, 14, 20)

    value = ctypes.c_double()
    for index, want in enumerate(layout["header"][:14]):
        assert lib.r6_engine_runtime_header(ctypes.byref(view), index,
                                            ctypes.byref(value)) == R6_OK
        assert value.value == float(want)
    for index, name in enumerate(engine_runtime_catalog.CONSTANT_NAMES):
        assert lib.r6_engine_runtime_constant(ctypes.byref(view), index,
                                              ctypes.byref(value)) == R6_OK
        assert value.value == float(layout["runtime_constants"][name])
    for sound, record in enumerate(layout["sound_records"]):
        lex8 = ctypes.c_double()
        lex13 = ctypes.c_double()
        assert lib.r6_engine_runtime_sound(ctypes.byref(view), sound,
                                           ctypes.byref(lex8),
                                           ctypes.byref(lex13)) == R6_OK
        assert (lex8.value, lex13.value) == (float(record[8]),
                                             float(record[13]))

    pow_cb = test_envelope_runtime.POW_FN(
        lambda user, base, exponent: math.pow(base, exponent))
    exp2_cb = test_envelope_runtime.EXP2_FN(
        lambda user, exponent: math.pow(2.0, exponent))
    math_sink = test_envelope_runtime.Math(None, pow_cb, exp2_cb)
    native_state = State()
    results = (LayerResult * 16)()
    count = ctypes.c_uint32()
    checked = 0

    for sound in range(data["counts"]["sounds"]):
        for variant, (rpm, request_offset) in enumerate(
                ((3000, 0), (1500, 25))):
            current = 3000 if variant == 0 else 50
            values = state_values(current, variant)
            assert lib.r6_engine_state_init(ctypes.byref(native_state),
                                            rpm) == R6_OK
            native_state.current = current
            native_state.request_offset = request_offset
            native_state.base = (ctypes.c_double * 5)(*values["base"])
            native_state.layer_base = (ctypes.c_double * 16)(
                *values["layer_base"])
            native_state.flag = 1 if values["flag"] else 0
            native_state.throttle = values["throttle"]
            native_state.floors = ((ctypes.c_double * 3) * 3)(
                *[(ctypes.c_double * 3)(*row) for row in values["floors"]])
            native_state.smooth34 = values["smooth34"]
            native_state.smooth4f = values["smooth4f"]
            native_state.smooth20 = values["smooth20"]
            native_state.f134 = values["f134"]
            native_state.f2d = values["f2d"]
            native_state.sub = values["sub"]
            native_state.curve_scale = values["curve_scale"]

            assert lib.r6_engine_eval_layers(
                ctypes.byref(view), esnd_buffer, len(esnd_blob), sound,
                ctypes.byref(native_state), ctypes.byref(math_sink), results,
                16, ctypes.byref(count)) == R6_OK
            assert count.value == 16
            want = engine_sound.layer_outputs(layout, sound, rpm, values,
                                              request_offset)
            for index, row in enumerate(want):
                got = results[index]
                assert (got.layer, got.tone, got.source) == \
                    (row["layer"], row["tone"],
                     engine_sound_catalog.SOURCES[row["source"]]), \
                    (sound, variant, index)
                assert (got.pitch, got.level) == \
                    (row["pitch"], row["level"]), \
                    (sound, variant, index, got.pitch, got.level,
                     row["pitch"], row["level"])
                assert abs(got.volume - row["volume"]) < 1e-9, \
                    (sound, variant, index, got.volume, row["volume"])
            checked += 16

    empty = test_envelope_runtime.Math()
    empty.pow_value = pow_cb
    empty.exp2_value = ctypes.cast(ctypes.c_void_p(),
                                   test_envelope_runtime.EXP2_FN)
    assert lib.r6_engine_eval_layers(ctypes.byref(view), esnd_buffer,
                                     len(esnd_blob), 0,
                                     ctypes.byref(native_state),
                                     ctypes.byref(empty), results, 16,
                                     ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_engine_eval_layers(ctypes.byref(view), esnd_buffer,
                                     len(esnd_blob), 224,
                                     ctypes.byref(native_state),
                                     ctypes.byref(math_sink), results, 16,
                                     ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_engine_eval_layers(ctypes.byref(view), esnd_buffer,
                                     len(esnd_blob), 0,
                                     ctypes.byref(native_state),
                                     ctypes.byref(math_sink), results, 15,
                                     ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_engine_state_init(None, 0) == R6_ERR_ARG
    print("engine runtime: %d layer outputs across %d sounds match the Python "
          "state evaluator; bad sound/capacity/hooks: OK" %
          (checked, data["counts"]["sounds"]))


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
