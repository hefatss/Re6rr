"""Check the freestanding mixer arithmetic and bus byte layout."""

import ctypes
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

BUS_COUNT = 0x44
BUS_STRIDE = 0x48


class Bus(ctypes.Structure):
    _fields_ = [("volume", ctypes.c_float), ("target", ctypes.c_float),
                ("step", ctypes.c_float), ("frames", ctypes.c_uint32),
                ("mode", ctypes.c_uint32)]


def configure(lib):
    for name, argtypes in (
            ("r6_mixer_bus_read", [ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.c_uint32, ctypes.POINTER(Bus)]),
            ("r6_mixer_bus_write", [ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.c_uint32, ctypes.POINTER(Bus)]),
            ("r6_mixer_bus_fade", [ctypes.POINTER(Bus), ctypes.c_float,
                                   ctypes.c_uint32]),
            ("r6_mixer_db_to_volume", [ctypes.c_float, ctypes.c_float,
                                       ctypes.c_float, ctypes.c_float,
                                       ctypes.POINTER(ctypes.c_float)]),
            ("r6_mixer_volume_to_db", [ctypes.c_float, ctypes.c_float,
                                       ctypes.c_float, ctypes.c_float,
                                       ctypes.POINTER(ctypes.c_float)])):
        function = getattr(lib, name)
        function.restype = ctypes.c_int
        function.argtypes = argtypes


def bus_values(bus):
    return (bus.volume, bus.target, bus.step, bus.frames, bus.mode)


def assert_bus(bus, state):
    assert abs(bus.volume - state["volume"]) < 1e-6
    assert abs(bus.target - state["target"]) < 1e-6
    assert abs(bus.step - state["step"]) < 1e-6
    assert (bus.frames, bus.mode) == (state["frames"], state["mode"])


def check(dump):
    facts = audio_events.mixer_facts()
    assert facts["bus_count"] == BUS_COUNT and \
        facts["bus_stride"] == BUS_STRIDE
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)

    raw = bytearray(BUS_COUNT * BUS_STRIDE)
    base = 7 * BUS_STRIDE
    struct.pack_into("<f", raw, base + 0x00, 1.25)
    struct.pack_into("<I", raw, base + 0x10, 2)
    struct.pack_into("<I", raw, base + 0x14, 9)
    struct.pack_into("<f", raw, base + 0x18, 2.0)
    struct.pack_into("<f", raw, base + 0x1C, 0.125)
    buffer = ctypes.create_string_buffer(bytes(raw), len(raw))
    read = Bus()
    assert lib.r6_mixer_bus_read(buffer, len(raw), 7,
                                 ctypes.byref(read)) == R6_OK
    assert bus_values(read) == (1.25, 2.0, 0.125, 9, 2)

    write = Bus(0.75, 1.5, -0.25, 4, 0)
    assert lib.r6_mixer_bus_write(buffer, len(raw), 8,
                                  ctypes.byref(write)) == R6_OK
    at = 8 * BUS_STRIDE
    assert struct.unpack_from("<f", buffer.raw, at + 0x00)[0] == 0.75
    assert struct.unpack_from("<I", buffer.raw, at + 0x10)[0] == 0
    assert struct.unpack_from("<I", buffer.raw, at + 0x14)[0] == 4
    assert struct.unpack_from("<f", buffer.raw, at + 0x18)[0] == 1.5
    assert struct.unpack_from("<f", buffer.raw, at + 0x1C)[0] == -0.25
    assert lib.r6_mixer_bus_read(buffer, len(raw), BUS_COUNT,
                                 ctypes.byref(read)) == R6_ERR_ARG
    assert lib.r6_mixer_bus_read(buffer, len(raw) - 1, 0,
                                 ctypes.byref(read)) == R6_ERR_ARG

    state = {"volume": 1.0, "target": 1.0, "step": 0.0, "frames": 0,
             "mode": 0}
    bus = Bus(1.0, 1.0, 0.0, 0, 0)
    assert lib.r6_mixer_bus_fade(ctypes.byref(bus), 2.0, 10) == R6_OK
    audio_events.bus_fade(state, 2.0, 10)
    assert_bus(bus, state)
    assert lib.r6_mixer_bus_fade(ctypes.byref(bus), 0.5, 0) == R6_OK
    audio_events.bus_fade(state, 0.5, 0)
    assert_bus(bus, state)
    assert lib.r6_mixer_bus_fade(None, 1.0, 1) == R6_ERR_ARG

    lo, mid, hi = -96.0, 6.0, 2.0
    out = ctypes.c_float()
    for db in (-100.0, -96.0, -48.0, 0.0, 5.999, 6.0, 12.0, 24.0):
        assert lib.r6_mixer_db_to_volume(db, lo, mid, hi,
                                         ctypes.byref(out)) == R6_OK
        want = audio_events.decibels_to_volume(db, lo, mid, hi)
        assert abs(out.value - want) < 1e-5, db
        assert lib.r6_mixer_volume_to_db(out.value, lo, mid, hi,
                                         ctypes.byref(out)) == R6_OK
        if want > 0:
            assert abs(out.value - db) < 1e-3, db
    assert lib.r6_mixer_db_to_volume(0.0, 0.0, 0.0, 2.0,
                                     ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_mixer_volume_to_db(0.0, 0.0, 0.0, 2.0,
                                     ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_mixer_db_to_volume(0.0, lo, mid, hi, None) == R6_ERR_ARG
    print("mixer runtime: 68 buses at 0x48 stride, fade and dB conversions "
          "match the recovered ABI; bad index/size/calibration: OK")


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
