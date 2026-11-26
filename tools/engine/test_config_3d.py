"""Check the C config_3d.bin reader against the Python recovery."""

import ctypes
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6

POW_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                          ctypes.c_double, ctypes.c_double)
EXP2_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                           ctypes.c_double)


class Math(ctypes.Structure):
    _fields_ = [("user", ctypes.c_void_p), ("pow_value", POW_FN),
                ("exp2_value", EXP2_FN)]


class Record(ctypes.Structure):
    _fields_ = [("flags", ctypes.c_uint32), ("db_start", ctypes.c_float),
                ("angle", ctypes.c_float), ("db_end", ctypes.c_float),
                ("raw", ctypes.c_uint32 * 3)]


class Section(ctypes.Structure):
    _fields_ = [("records", Record * 10), ("tail", ctypes.c_uint32 * 6)]


class View(ctypes.Structure):
    _fields_ = [("version", ctypes.c_ubyte * 3),
                ("count", ctypes.c_uint32), ("stride", ctypes.c_uint32),
                ("floats", ctypes.c_float * 4),
                ("sections", ctypes.POINTER(Section))]


def configure(lib):
    lib.r6_config_3d_init.restype = ctypes.c_int
    lib.r6_config_3d_init.argtypes = [
        ctypes.POINTER(View), ctypes.c_void_p, ctypes.c_size_t,
        ctypes.POINTER(Section), ctypes.c_uint32]
    lib.r6_config_3d_amplitude.restype = ctypes.c_int
    lib.r6_config_3d_amplitude.argtypes = [
        ctypes.POINTER(Math), ctypes.c_double, ctypes.c_double,
        ctypes.POINTER(ctypes.c_double)]


def check(dump):
    raw = open(os.path.join(dump, "data", "sound", "config_3d.bin"),
               "rb").read()
    want = audio_events.parse_config_3d(raw)
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)

    source = ctypes.create_string_buffer(raw, len(raw))
    sections = (Section * 0x20)()
    view = View()
    assert lib.r6_config_3d_init(ctypes.byref(view), source, len(raw),
                                 sections, 0x20) == R6_OK
    assert list(view.version) == list(want["version"])
    assert (view.count, view.stride) == (want["count"], want["stride"])
    for index, value in enumerate(want["floats"]):
        assert abs(view.floats[index] - value) < 1e-5
    for index, section in enumerate(want["sections"]):
        for record, row in enumerate(section["records"]):
            got = sections[index].records[record]
            assert got.flags == row["flags"]
            assert got.db_start == row["db_start"]
            assert abs(got.angle - row["angle"]) < 1e-4
            assert got.db_end == row["db_end"]
            assert list(got.raw) == row["raw"]
        assert list(sections[index].tail) == section["tail"]

    bad_version = bytearray(raw)
    bad_version[4] = 9
    bad_stride = bytearray(raw)
    struct.pack_into("<i", bad_stride, 12, 0x131)
    bad_count = bytearray(raw)
    struct.pack_into("<i", bad_count, 8, 0x21)
    for data, size, capacity, expected in (
            (source, 0x1F, 0x20, R6_ERR_BUFFER),
            (ctypes.create_string_buffer(bytes(bad_version)), len(raw),
             0x20, R6_ERR_FORMAT),
            (ctypes.create_string_buffer(bytes(bad_stride)), len(raw),
             0x20, R6_ERR_FORMAT),
            (ctypes.create_string_buffer(bytes(bad_count)), len(raw),
             0x20, R6_ERR_FORMAT),
            (source, len(raw) - 1, 0x20, R6_ERR_FORMAT),
            (source, len(raw), 4, R6_ERR_BUFFER)):
        assert lib.r6_config_3d_init(ctypes.byref(view), data, size,
                                     sections, capacity) == expected
    assert lib.r6_config_3d_init(None, source, len(raw), sections,
                                 0x20) == R6_ERR_BUFFER
    assert lib.r6_config_3d_init(ctypes.byref(view), source, len(raw), None,
                                 0x20) == R6_ERR_BUFFER

    empty = bytearray(raw)
    struct.pack_into("<i", empty, 8, 0)
    empty_view = View()
    assert lib.r6_config_3d_init(ctypes.byref(empty_view),
                                 ctypes.create_string_buffer(bytes(empty)),
                                 len(empty), None, 0) == R6_OK
    assert empty_view.count == 0 and not empty_view.sections

    pow_cb = POW_FN(lambda user, base, exponent: math.pow(base, exponent))
    exp2_cb = EXP2_FN(lambda user, exponent: math.pow(2.0, exponent))
    sink = Math(None, pow_cb, exp2_cb)
    out = ctypes.c_double()
    for db in (-96.0, -48.0, 0.0, 6.0):
        assert lib.r6_config_3d_amplitude(ctypes.byref(sink), db, -96.0,
                                          ctypes.byref(out)) == R6_OK
        want_db = audio_events.decibels_to_amplitude(db, -96.0)
        assert abs(out.value - want_db) < 1e-9, (db, out.value, want_db)
    assert lib.r6_config_3d_amplitude(ctypes.byref(Math()), 0.0, -96.0,
                                      ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_config_3d_amplitude(ctypes.byref(sink), 0.0, -96.0,
                                      None) == R6_ERR_ARG
    print("config_3d: %d sections x 10 records and 6 tail words match Python; "
          "dB amplitudes and malformed headers: OK" % want["count"])


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
