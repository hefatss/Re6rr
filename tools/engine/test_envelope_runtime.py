"""Check the envelope curve port against the Python reference."""

import ctypes
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_tables  # noqa: E402
import engine_sound  # noqa: E402
import nub_audio  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1

POW_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                          ctypes.c_double, ctypes.c_double)
EXP2_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                           ctypes.c_double)


class Math(ctypes.Structure):
    _fields_ = [("user", ctypes.c_void_p), ("pow_value", POW_FN),
                ("exp2_value", EXP2_FN)]


class Result(ctypes.Structure):
    _fields_ = [("pitch", ctypes.c_int32), ("volume", ctypes.c_int32)]


def configure(lib):
    lib.r6_envelope_eval.restype = ctypes.c_int
    lib.r6_envelope_eval.argtypes = [
        ctypes.POINTER(Math), ctypes.POINTER(ctypes.c_int32),
        ctypes.c_int32, ctypes.c_double, ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double, ctypes.POINTER(Result)]


def check(dump):
    data = engine_sound.collect(dump)
    emtis = audio_tables.parse_emtis(os.path.join(
        dump, nub_audio.SOUND_DIR, "emtis.tbl"))
    header = engine_sound.parse_layout(emtis)["header"]
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)

    pow_cb = POW_FN(lambda user, base, exponent: math.pow(base, exponent))
    exp2_cb = EXP2_FN(lambda user, exponent: math.pow(2.0, exponent))
    math_sink = Math(None, pow_cb, exp2_cb)
    envelope = (ctypes.c_int32 * 5)()
    result = Result()
    amplitude = header[1]
    volume_base = 1000.0
    volume_scale = 0.25
    detune_divisor = header[0]
    curve_power = header[2]

    layers = 0
    for sound in range(data["counts"]["sounds"]):
        for row in data["envelope_layers"][str(sound)]:
            for index, value in enumerate(row["envelope"]):
                envelope[index] = value
            rpms = {0, 5000, row["envelope"][0], row["envelope"][1],
                    row["envelope"][3], row["envelope"][4]}
            for rpm in sorted(rpms):
                want = engine_sound.envelope_output(
                    row["envelope"], rpm, amplitude, volume_base,
                    volume_scale, header)
                assert lib.r6_envelope_eval(
                    ctypes.byref(math_sink), envelope, rpm, amplitude,
                    volume_base, volume_scale, detune_divisor,
                    curve_power, ctypes.byref(result)) == R6_OK
                assert (result.pitch, result.volume) == want, \
                    (sound, row["layer"], rpm)
            layers += 1

    assert lib.r6_envelope_eval(ctypes.byref(math_sink), envelope, 0,
                                amplitude, volume_base, volume_scale, 0.0,
                                curve_power, ctypes.byref(result)) == \
        R6_ERR_ARG
    assert lib.r6_envelope_eval(None, envelope, 0, amplitude, volume_base,
                                volume_scale, detune_divisor, curve_power,
                                ctypes.byref(result)) == R6_ERR_ARG
    empty = Math()
    empty.pow_value = pow_cb
    empty.exp2_value = ctypes.cast(ctypes.c_void_p(), EXP2_FN)
    assert lib.r6_envelope_eval(ctypes.byref(empty), envelope, 0, amplitude,
                                volume_base, volume_scale, detune_divisor,
                                curve_power, ctypes.byref(result)) == \
        R6_ERR_ARG
    assert lib.r6_envelope_eval(ctypes.byref(math_sink), None, 0, amplitude,
                                volume_base, volume_scale, detune_divisor,
                                curve_power, ctypes.byref(result)) == \
        R6_ERR_ARG
    assert lib.r6_envelope_eval(ctypes.byref(math_sink), envelope, 0, amplitude,
                                volume_base, volume_scale, detune_divisor,
                                curve_power, None) == R6_ERR_ARG
    print("envelope runtime: %d layers x 6 rpm points match the Python curve; "
          "missing math hooks and bad arguments: OK" % layers)


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
