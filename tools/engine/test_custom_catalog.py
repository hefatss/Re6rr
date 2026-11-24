"""ctypes checks for the packed customization catalog parser."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_engine import R6_OK, load_core  # noqa: E402
import custom_catalog  # noqa: E402

R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class Color(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint16), ("icon", ctypes.c_uint16),
        ("feel", ctypes.c_uint16), ("reserved", ctypes.c_uint16),
        ("body0", ctypes.c_float * 4), ("body1", ctypes.c_float * 4),
        ("spec", ctypes.c_float * 4), ("params", ctypes.c_float * 4),
        ("name", ctypes.c_char * 24),
    ]


class Wheel(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint16), ("reserved", ctypes.c_uint16),
        ("name", ctypes.c_char * 24), ("flags", ctypes.c_uint32),
        ("reserved2", ctypes.c_uint32 * 4),
    ]


class Aero(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint16), ("reserved", ctypes.c_uint16),
        ("name", ctypes.c_char * 48), ("flags", ctypes.c_uint32),
        ("reserved2", ctypes.c_uint32 * 2),
    ]


class Tune(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_char * 24),
        ("aero_category", ctypes.c_uint16),
        ("limited_parts", ctypes.c_uint16),
        ("pure_wheel_front", ctypes.c_uint8),
        ("pure_wheel_rear", ctypes.c_uint8),
        ("custom_wheel_front", ctypes.c_uint8),
        ("custom_wheel_rear", ctypes.c_uint8),
        ("change_tuning_disp", ctypes.c_uint8),
        ("custom_gt_wing", ctypes.c_uint8),
        ("wing_a_h", ctypes.c_uint16),
        ("wing_n", ctypes.c_uint16),
        ("default_color_count", ctypes.c_uint16),
        ("custom_color_count", ctypes.c_uint16),
        ("default_color_ids", ctypes.c_uint16 * 11),
        ("custom_color_ids", ctypes.c_uint16 * 40),
        ("flags", ctypes.c_uint32), ("reserved", ctypes.c_uint32),
        ("pad", ctypes.c_uint8 * 8),
    ]


class Tire(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_uint16), ("index", ctypes.c_uint16),
        ("value", ctypes.c_float),
    ]


class Catalog(ctypes.Structure):
    _fields_ = [
        ("colors", ctypes.c_void_p), ("wheels", ctypes.c_void_p),
        ("aeros", ctypes.c_void_p), ("tunes", ctypes.c_void_p),
        ("tires", ctypes.c_void_p),
        ("color_count", ctypes.c_size_t), ("wheel_count", ctypes.c_size_t),
        ("aero_count", ctypes.c_size_t), ("tune_count", ctypes.c_size_t),
        ("tire_count", ctypes.c_size_t),
    ]


def close(a, b):
    return abs(a - b) <= 1e-4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                      "r6_engine.dll"))
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--recon", default=os.path.join(ROOT, "docs", "recon"))
    args = parser.parse_args()

    lib = load_core(args.dll, args.dump)
    failures = []
    sections = custom_catalog.build(args.dump, args.recon)
    blob = custom_catalog.pack(sections)
    catalog = Catalog()

    lib.r6_custom_catalog_parse.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(Catalog)]
    lib.r6_custom_catalog_parse.restype = ctypes.c_int
    for section, cls, size in (
            ("color", Color, custom_catalog.COLOR_SIZE),
            ("wheel", Wheel, custom_catalog.WHEEL_SIZE),
            ("aero", Aero, custom_catalog.AERO_SIZE),
            ("tune", Tune, custom_catalog.TUNE_SIZE),
            ("tire", Tire, custom_catalog.TIRE_SIZE)):
        if ctypes.sizeof(cls) != size:
            failures.append("%s ctypes size %d, expected %d" %
                            (section, ctypes.sizeof(cls), size))

    rc = lib.r6_custom_catalog_parse(blob, len(blob), ctypes.byref(catalog))
    if rc != R6_OK:
        failures.append("parse rc=%d" % rc)
        for failure in failures:
            print("FAIL " + failure)
        return 1
    counts = (catalog.color_count, catalog.wheel_count, catalog.aero_count,
              catalog.tune_count, catalog.tire_count)
    expected = tuple(len(sections[key]) for key in
                     ("colors", "wheels", "aeros", "tunes", "tires"))
    if counts != expected:
        failures.append("counts %r, expected %r" % (counts, expected))
    else:
        print("  custom catalog: %d colors, %d wheels, %d parts, "
              "%d tunes, %d scales" % counts)

    lib.r6_custom_catalog_color.argtypes = [
        ctypes.POINTER(Catalog), ctypes.c_size_t, ctypes.POINTER(Color)]
    lib.r6_custom_catalog_wheel.argtypes = [
        ctypes.POINTER(Catalog), ctypes.c_size_t, ctypes.POINTER(Wheel)]
    lib.r6_custom_catalog_aero.argtypes = [
        ctypes.POINTER(Catalog), ctypes.c_size_t, ctypes.POINTER(Aero)]
    lib.r6_custom_catalog_tune.argtypes = [
        ctypes.POINTER(Catalog), ctypes.c_size_t, ctypes.POINTER(Tune)]
    lib.r6_custom_catalog_tire.argtypes = [
        ctypes.POINTER(Catalog), ctypes.c_size_t, ctypes.POINTER(Tire)]
    for name in ("color", "wheel", "aero", "tune", "tire"):
        getattr(lib, "r6_custom_catalog_" + name).restype = ctypes.c_int
    for name in ("color", "wheel", "aero", "tune", "tire", "find_color",
                 "find_wheel", "find_aero", "find_tune"):
        function = getattr(lib, "r6_custom_catalog_" + name)
        function.argtypes = ([ctypes.POINTER(Catalog), ctypes.c_uint16]
                             if name == "find_color" else
                             [ctypes.POINTER(Catalog), ctypes.c_char_p]
                             if name.startswith("find_") else
                             [ctypes.POINTER(Catalog), ctypes.c_size_t,
                              ctypes.c_void_p])

    bad = 0
    colors = sections["colors"]
    for index in (0, 1, 83, len(colors) - 1):
        color = Color()
        if lib.r6_custom_catalog_color(ctypes.byref(catalog), index,
                                       ctypes.byref(color)) != R6_OK:
            bad += 1
            continue
        entry = colors[index]
        if (color.id != entry["id"] or color.icon != entry["icon"] or
                color.feel != entry["feel"] or
                any(not close(a, b) for a, b in
                    zip(color.body0, entry["body0"])) or
                color.name.rstrip(b"\0") !=
                custom_catalog.text_field(entry["name"], 24).rstrip(b"\0")):
            bad += 1
    wheels = sections["wheels"]
    for index in (0, 26, len(wheels) - 1):
        wheel = Wheel()
        if lib.r6_custom_catalog_wheel(ctypes.byref(catalog), index,
                                       ctypes.byref(wheel)) != R6_OK:
            bad += 1
            continue
        entry = wheels[index]
        if wheel.id != entry["id"] or \
                wheel.name.rstrip(b"\0") != \
                custom_catalog.text_field(entry["name"], 24).rstrip(b"\0"):
            bad += 1
    aeros = sections["aeros"]
    for index in (0, 23, len(aeros) - 1):
        aero = Aero()
        if lib.r6_custom_catalog_aero(ctypes.byref(catalog), index,
                                      ctypes.byref(aero)) != R6_OK:
            bad += 1
            continue
        entry = aeros[index]
        if aero.id != entry["id"] or aero.flags != entry["flags"]:
            bad += 1
    tunes = sections["tunes"]
    for index in (0, 50, len(tunes) - 1):
        tune = Tune()
        if lib.r6_custom_catalog_tune(ctypes.byref(catalog), index,
                                      ctypes.byref(tune)) != R6_OK:
            bad += 1
            continue
        entry = tunes[index]
        if (tune.aero_category != entry["aero_category"] or
                tune.pure_wheel_front != entry["pure_wheel_front"] or
                tune.wing_a_h != entry["wing_a_h"] or
                tune.custom_color_count != entry["custom_color_count"] or
                list(tune.custom_color_ids) != entry["custom_color_ids"]):
            bad += 1
    tires = sections["tires"]
    for index in (0, 10, len(tires) - 1):
        tire = Tire()
        if lib.r6_custom_catalog_tire(ctypes.byref(catalog), index,
                                      ctypes.byref(tire)) != R6_OK or \
                not close(tire.value, tires[index]["value"]):
            bad += 1
    if bad:
        failures.append("%d/%d sampled records differ" % (bad, 13))
    else:
        print("  sampled records from all five sections round-trip")

    checks = (
        ("find_color", 83, 83),
        ("find_wheel", b"SWH_RC3", 0),
        ("find_aero", b"CAR_PARTS_ID_AERO_01", None),
        ("find_tune", b"PLC_AE86", None),
    )
    for name, key, expected_index in checks:
        found = getattr(lib, "r6_custom_catalog_" + name)(
            ctypes.byref(catalog), key)
        expected_value = expected_index
        if expected_value is None:
            if name == "find_aero":
                expected_value = next(i for i, row in enumerate(aeros)
                                      if row["name"] == key.decode())
            else:
                expected_value = next(i for i, row in enumerate(tunes)
                                      if row["model"] == key.decode())
        if found != expected_value:
            failures.append("%s(%r) = %d, expected %d" %
                            (name, key, found, expected_value))
    if lib.r6_custom_catalog_find_color(ctypes.byref(catalog), 9999) != -1:
        failures.append("unknown colour matched")
    if lib.r6_custom_catalog_find_wheel(ctypes.byref(catalog),
                                        b"SWH_NOPE") != -1:
        failures.append("unknown wheel matched")
    if lib.r6_custom_catalog_find_tune(ctypes.byref(catalog),
                                       b"PLC_NOPE") != -1:
        failures.append("unknown tune matched")

    bad = bytearray(blob)
    bad[8:12] = struct.pack("<I", 2)
    if lib.r6_custom_catalog_parse(bytes(bad), len(bad),
                                   ctypes.byref(catalog)) != R6_ERR_FORMAT:
        failures.append("bad version accepted")
    bad = bytearray(blob)
    bad[4] = ord("X")
    if lib.r6_custom_catalog_parse(bytes(bad), len(bad),
                                   ctypes.byref(catalog)) != R6_ERR_FORMAT:
        failures.append("bad magic accepted")
    if lib.r6_custom_catalog_parse(bytes(blob[:-1]), len(blob) - 1,
                                   ctypes.byref(catalog)) != R6_ERR_FORMAT:
        failures.append("truncated blob accepted")
    if lib.r6_custom_catalog_parse(bytes(blob), len(blob), None) != R6_ERR_ARG:
        failures.append("null catalog accepted")

    if failures:
        for failure in failures:
            print("FAIL " + failure)
        return 1
    print("all customization catalog checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
