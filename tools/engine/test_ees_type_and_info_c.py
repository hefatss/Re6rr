"""Check the EES camera type filter and car_info id reader in C."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import ees_scene  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1


def check(dump, lib):
    lib.r6_ees_camera_accept_type.restype = ctypes.c_int
    lib.r6_ees_camera_accept_type.argtypes = [ctypes.c_int32]
    lib.r6_ees_car_info.restype = ctypes.c_int
    lib.r6_ees_car_info.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.c_uint32, ctypes.POINTER(ctypes.c_int32)]
    for kind in (-1, 0, 1, 2, 3, 100):
        assert bool(lib.r6_ees_camera_accept_type(kind)) == (kind in (0, 2))

    root = os.path.join(dump, ees_scene.SCENE_DIR)
    accepted = 0
    files = 0
    for directory, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".EES"):
                continue
            with open(os.path.join(directory, name), "rb") as stream:
                raw = stream.read()
            header = ees_scene.parse_ees(raw)
            if header["kind"] != "cam":
                continue
            files += 1
            array = header["arrays"][1]
            for index in range(array["count"]):
                kind, = struct.unpack_from("<i", raw,
                                           array["offset"] +
                                           index * ees_fields.CAMERA_STRIDE)
                assert bool(lib.r6_ees_camera_accept_type(kind)) == \
                    (kind in (0, 2))
                accepted += kind in (0, 2)
    assert files == 720 and accepted > 0

    path = os.path.join(dump, ees_scene.SCENE_DIR, "ESeries_001",
                        "FrontEvent", "CarData0.EES")
    with open(path, "rb") as stream:
        raw = stream.read()
    header = ees_scene.parse_ees(raw)
    array = header["arrays"][2]
    source = ctypes.create_string_buffer(raw, len(raw))
    value = ctypes.c_int32()
    for index in range(array["count"]):
        offset = array["offset"] + index * ees_fields.CAR_INFO_STRIDE
        assert lib.r6_ees_car_info(source, len(raw), offset,
                                   ctypes.byref(value)) == R6_OK
        want, = struct.unpack_from("<i", raw, offset)
        assert value.value == want, (index, value.value, want)
    assert lib.r6_ees_car_info(source, len(raw), len(raw),
                               ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_ees_car_info(source, len(raw), array["offset"],
                               None) == R6_ERR_ARG
    assert lib.r6_ees_car_info(None, len(raw), array["offset"],
                               ctypes.byref(value)) == R6_ERR_ARG
    print("EES type/info: %d cameras checked for FUN_1401ca060 type 0/2 "
          "filter, %d ids match in the shipped car_info array; short and "
          "null inputs rejected" % (files, array["count"]))


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
