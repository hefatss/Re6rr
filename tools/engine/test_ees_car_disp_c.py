"""Check the C car_disp reader against the shipped EES record oracle."""

import ctypes
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import ees_scene  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1


class Record(ctypes.Structure):
    _fields_ = [("car_id", ctypes.c_int32),
                ("flags", ctypes.c_uint8),
                ("reserved", ctypes.c_uint8 * 11),
                ("matrix", ctypes.c_float * 16),
                ("reserved2", ctypes.c_uint8 * 0x100),
                ("yaw", ctypes.c_float),
                ("yaw_units", ctypes.c_int64)]


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_ees_car_disp.restype = ctypes.c_int
    lib.r6_ees_car_disp.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.c_uint32, ctypes.POINTER(Record)]

    path = os.path.join(dump, ees_scene.SCENE_DIR, "ESeries_001",
                        "FrontEvent", "CarData0.EES")
    with open(path, "rb") as stream:
        raw = stream.read()
    header = ees_scene.parse_ees(raw)
    car_offset = header["arrays"][0]["offset"]
    rows = ees_fields.car_rows(raw, header)
    assert len(rows) == 10800

    source = ctypes.create_string_buffer(raw, len(raw))
    record = Record()
    for index, want in enumerate(rows):
        offset = car_offset + index * ees_fields.CAR_DISP_STRIDE
        assert lib.r6_ees_car_disp(source, len(raw), offset,
                                   ctypes.byref(record)) == R6_OK
        assert record.car_id == want["car_id"], (index, "car_id")
        assert record.flags == want["flags"], (index, "flags")
        assert list(record.matrix) == list(want["matrix"]), (index, "matrix")
        if math.isnan(want["yaw"]):
            assert math.isnan(record.yaw), (index, "yaw")
        else:
            assert record.yaw == want["yaw"], (index, "yaw")
        assert record.yaw_units == want["yaw_units"], (index, "yaw_units")

    import struct
    for bits in (0x7FC00000, 0x7F800000, 0xFF800000):
        synthetic = bytearray(0x180)
        struct.pack_into("<I", synthetic, 0x150, bits)
        assert lib.r6_ees_car_disp(bytes(synthetic), len(synthetic), 0,
                                   ctypes.byref(record)) == R6_OK
        assert record.yaw_units == 0

    assert lib.r6_ees_car_disp(source, len(raw), len(raw),
                               ctypes.byref(record)) == R6_ERR_ARG
    assert lib.r6_ees_car_disp(source, len(raw), car_offset,
                               None) == R6_ERR_ARG
    assert lib.r6_ees_car_disp(None, len(raw), car_offset,
                               ctypes.byref(record)) == R6_ERR_ARG

    unusual = [row for row in rows if not math.isfinite(row["yaw"])]
    print("car_disp: all %d shipped records match car_disp_record(); %d "
          "non-finite yaw cases; short offset and null arguments rejected" %
          (len(rows), len(unusual)))


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
