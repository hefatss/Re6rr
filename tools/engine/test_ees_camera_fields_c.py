"""Check the C EES camera field reader against the shipped native logger map."""

import ctypes
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

I32 = "m_CamType m_StratFrame m_FieldAngleCalcId m_GlobalLookAt m_LookAtId " \
      "m_TransCalcId m_RotCalcId m_OpRotZCalcId m_OfsetCalcId " \
      "m_StartConnection m_EndConnection".split()
F32 = "m_ActFrame m_StratFieldAngle m_EndFieldAngle m_LookAtStartRenge " \
      "m_LookAtStartCamRotX m_LookAtStartCamRotY m_LookAtStartCamRotZ " \
      "m_LookAtEndRenge m_LookAtEndCamRotX m_LookAtEndCamRotY " \
      "m_LookAtEndCamRotZ m_StratOpRotZ m_EndOpRotZ " \
      "m_LookAtStartOfsetPosX m_LookAtStartOfsetPosY " \
      "m_LookAtStartOfsetPosZ m_LookAtEndOfsetPosX m_LookAtEndOfsetPosY " \
      "m_LookAtEndOfsetPosZ".split()
ORDER = ["m_CamType", "m_StratFrame", "m_ActFrame", "m_WiatMode",
         "m_StratFieldAngle", "m_EndFieldAngle", "m_FieldAngleCalcId",
         "m_GlobalLookAt", "m_LookAtId", "m_LookAtStartRenge",
         "m_LookAtStartCamRotX", "m_LookAtStartCamRotY",
         "m_LookAtStartCamRotZ", "m_LookAtEndRenge", "m_LookAtEndCamRotX",
         "m_LookAtEndCamRotY", "m_LookAtEndCamRotZ", "m_TransCalcId",
         "m_RotCalcId", "m_StratOpRotZ", "m_EndOpRotZ", "m_OpRotZCalcId",
         "m_LookAtStartOfsetPosX", "m_LookAtStartOfsetPosY",
         "m_LookAtStartOfsetPosZ", "m_LookAtEndOfsetPosX",
         "m_LookAtEndOfsetPosY", "m_LookAtEndOfsetPosZ", "m_OfsetCalcId",
         "m_StartConnection", "m_EndConnection"]


class Fields(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int32 if name in I32 else
                 ctypes.c_float if name in F32 else ctypes.c_uint8)
                for name in ORDER]


def check(dump):
    assert len(ees_fields.CAMERA_FIELDS) == len(ORDER) == 31
    assert list(ees_fields.CAMERA_FIELDS) == ORDER
    path = os.path.join(dump, ees_scene.SCENE_DIR,
                        "ESeries_002", "FrontEvent", "CamData.EES")
    with open(path, "rb") as stream:
        raw = stream.read()
    header = ees_scene.parse_ees(raw)
    camera_offset = header["arrays"][1]["offset"]
    rows = ees_fields.camera_rows(raw, header)
    assert len(rows) == 255

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_ees_camera_fields.restype = ctypes.c_int
    lib.r6_ees_camera_fields.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_uint32,
                                        ctypes.POINTER(Fields)]
    source = ctypes.create_string_buffer(raw, len(raw))
    fields = Fields()
    for index in range(len(rows)):
        offset = camera_offset + index * ees_fields.CAMERA_STRIDE
        assert lib.r6_ees_camera_fields(source, len(raw), offset,
                                        ctypes.byref(fields)) == R6_OK
        want = ees_fields.camera_fields(raw, offset)
        for name in ORDER:
            assert getattr(fields, name) == want[name], (index, name)
    assert getattr(fields, "m_CamType") == -1
    assert getattr(fields, "m_WiatMode") == 1

    assert lib.r6_ees_camera_fields(source, len(raw), len(raw),
                                    ctypes.byref(fields)) == R6_ERR_ARG
    assert lib.r6_ees_camera_fields(source, len(raw), camera_offset,
                                    None) == R6_ERR_ARG
    assert lib.r6_ees_camera_fields(None, len(raw), camera_offset,
                                    ctypes.byref(fields)) == R6_ERR_ARG
    print("EES camera fields: all 31 named fields match on 255 shipped "
          "records; sentinel, short offset and null arguments checked")


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
