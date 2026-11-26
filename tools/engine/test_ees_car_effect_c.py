"""Check the C car_effect copy against the recovered native field map."""

import ctypes
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1


def check(dump):
    mapping = ees_fields.CAR_EFFECT_COPY
    assert len(mapping) == 40
    assert len(set(destination for _, destination, _ in mapping)) == 40

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_ees_car_effect_copy.restype = ctypes.c_int
    lib.r6_ees_car_effect_copy.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_void_p, ctypes.c_size_t]

    out = ctypes.create_string_buffer(0xE0)
    rng = random.Random(0x1401CC390)
    for _case in range(32):
        source = bytes(rng.randrange(256) for _ in range(0xA0))
        want = bytearray(0xE0)
        for src, destination, width in mapping:
            want[destination:destination + width] = \
                source[src:src + width]
        assert lib.r6_ees_car_effect_copy(source, len(source), out,
                                          len(out)) == R6_OK
        assert out.raw == bytes(want)

    source = ctypes.create_string_buffer(bytes(0xA0), 0xA0)
    assert lib.r6_ees_car_effect_copy(source, 0x9F, out, len(out)) == \
        R6_ERR_ARG
    assert lib.r6_ees_car_effect_copy(source, len(source), out, 0xDF) == \
        R6_ERR_ARG
    assert lib.r6_ees_car_effect_copy(None, len(source), out,
                                     len(out)) == R6_ERR_ARG
    assert lib.r6_ees_car_effect_copy(source, len(source), None,
                                     len(out)) == R6_ERR_ARG
    print("car_effect copy: 40 native field copies match on 32 records; "
          "short source/destination and null arguments rejected")


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
