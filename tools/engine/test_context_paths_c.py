"""Check C Lua context path templates against the shipped loader oracle."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import contexts  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
PATH_CAP = 0x100
COUNTS = (3, 3, 2, 1, 3)


def car_models(dump):
    pos = os.path.join(dump, "data", "car", "position", "pos")
    spec = os.path.join(dump, "data", "car", "specification")
    cars = sorted(name[10:-4] for name in os.listdir(pos)
                  if name.startswith("getTirePos_") and name.endswith(".lua"))
    models = sorted(name[:-17] for name in os.listdir(spec)
                    if name.endswith("_Specification.lua"))
    pairs = [(name, name) for name in models]
    for car in cars:
        base = car.split("_", 1)[0]
        exact = [model for model in models if model == base]
        pairs.append((car, exact[0] if exact else car))
    return pairs


def check(dump, lib):
    lib.r6_context_path.restype = ctypes.c_int
    lib.r6_context_path.argtypes = [ctypes.c_int, ctypes.c_int,
                                    ctypes.c_char_p, ctypes.c_char_p,
                                    ctypes.c_char_p, ctypes.c_size_t]
    pairs = car_models(dump)
    assert len(pairs) >= 151
    path = ctypes.create_string_buffer(PATH_CAP)
    for car, model in pairs:
        got = []
        for group, count in enumerate(COUNTS):
            for index in range(count):
                assert lib.r6_context_path(group, index,
                                           car.encode("ascii"),
                                           model.encode("ascii"),
                                           path, len(path)) == R6_OK
                relative = path.value.decode("ascii")
                if os.path.isfile(os.path.join(
                        dump, relative.replace("/", os.sep))):
                    got.append(relative)
        want = [os.path.relpath(item, dump).replace(os.sep, "/")
                for _name, names in contexts.context(dump, car, model)
                for item in names]
        assert got == want, (car, model, got, want)

    assert lib.r6_context_path(5, 0, b"PLC_BNR34", b"PLC_BNR34", path,
                               len(path)) == R6_ERR_NOT_FOUND
    assert lib.r6_context_path(0, 3, b"PLC_BNR34", b"PLC_BNR34", path,
                               len(path)) == R6_ERR_NOT_FOUND
    assert lib.r6_context_path(0, 0, b"../bad", b"PLC_BNR34", path,
                               len(path)) == R6_ERR_ARG
    assert lib.r6_context_path(0, 0, b"PLC_BNR34", None, path,
                               len(path)) == R6_ERR_ARG
    assert lib.r6_context_path(0, 0, b"PLC_BNR34", b"PLC_BNR34", path,
                               8) == R6_ERR_BUFFER
    assert lib.r6_context_path(0, 0, b"PLC_BNR34", b"PLC_BNR34", None,
                               len(path)) == R6_ERR_ARG
    print("context paths: %d car/model pairs match contexts.context(); bad "
          "set, index, name and capacity rejected" % len(pairs))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(args.dump, lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
