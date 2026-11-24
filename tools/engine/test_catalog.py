"""ctypes checks for the packed car catalog parser."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_engine import R6_OK, load_core  # noqa: E402
import car_catalog  # noqa: E402
import car_mapping  # noqa: E402

R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6

MODEL_SIZE = 24
NAME_SIZE = 64
MAKER_SIZE = 24


class CarInfo(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_char * MODEL_SIZE),
        ("name", ctypes.c_char * NAME_SIZE),
        ("maker", ctypes.c_char * MAKER_SIZE),
        ("model_id", ctypes.c_uint16),
        ("visual_model_id", ctypes.c_uint16),
        ("horsepower", ctypes.c_uint16),
        ("engine_cc", ctypes.c_uint16),
        ("drive", ctypes.c_uint8),
        ("mission", ctypes.c_uint8),
        ("flags", ctypes.c_uint8),
        ("maker_id_low", ctypes.c_uint8),
        ("tire_front", ctypes.c_float),
        ("tire_rear", ctypes.c_float),
        ("tire_width_front", ctypes.c_float),
        ("tire_width_rear", ctypes.c_float),
        ("maker_id", ctypes.c_uint32),
    ]


def text(raw, encoding="cp932"):
    return raw.split(b"\0", 1)[0].decode(encoding, "replace")


def bytes_of(value, size, encoding="cp932"):
    raw = value.encode(encoding, "replace")[:size - 1]
    return raw + b"\0" * (size - len(raw))


def close(a, b):
    return abs(a - b) <= 1e-4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                      "r6_engine.dll"))
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()

    lib = load_core(args.dll, args.dump)
    failures = []
    entries = car_catalog.catalog(args.dump)
    mappings = car_mapping.map_characters(args.dump)
    mapped = [row for row in mappings if row["model"]]
    blob = car_catalog.pack(entries, mappings)
    expected_size = (car_catalog.HEADER_SIZE +
                     car_catalog.RECORD_SIZE * len(entries) +
                     car_catalog.MAP_SIZE * len(mapped))
    if len(entries) < 100:
        failures.append("only %d cars discovered" % len(entries))
    if len(blob) != expected_size:
        failures.append("blob size %d, expected %d" %
                        (len(blob), expected_size))

    lib.r6_car_catalog_parse.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(CarInfo),
        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    lib.r6_car_catalog_find_model.argtypes = [
        ctypes.POINTER(CarInfo), ctypes.c_size_t, ctypes.c_char_p]
    lib.r6_car_catalog_find_model.restype = ctypes.c_int
    lib.r6_car_catalog_find_id.argtypes = [ctypes.POINTER(CarInfo),
                                           ctypes.c_size_t, ctypes.c_uint16]
    lib.r6_car_catalog_find_id.restype = ctypes.c_int
    lib.r6_car_catalog_character_count.argtypes = [ctypes.c_char_p,
                                                   ctypes.c_size_t]
    lib.r6_car_catalog_character_count.restype = ctypes.c_int
    lib.r6_car_catalog_find_character.argtypes = [ctypes.c_char_p,
                                                  ctypes.c_size_t,
                                                  ctypes.c_char_p]
    lib.r6_car_catalog_find_character.restype = ctypes.c_int

    needed = ctypes.c_size_t()
    rc = lib.r6_car_catalog_parse(blob, len(blob), None, 0,
                                  ctypes.byref(needed))
    if rc != R6_ERR_BUFFER or needed.value != len(entries):
        failures.append("capacity probe rc=%d count=%d" %
                        (rc, needed.value))

    cars = (CarInfo * len(entries))()
    count = ctypes.c_size_t()
    rc = lib.r6_car_catalog_parse(blob, len(blob), cars, len(entries),
                                  ctypes.byref(count))
    if rc != R6_OK or count.value != len(entries):
        failures.append("parse rc=%d count=%d" % (rc, count.value))

    mismatches = 0
    for index, entry in enumerate(entries):
        car = cars[index]
        if (car.model.rstrip(b"\0") != bytes_of(entry["model"], MODEL_SIZE).rstrip(b"\0") or
                car.name.rstrip(b"\0") != bytes_of(entry["name"], NAME_SIZE).rstrip(b"\0") or
                car.maker.rstrip(b"\0") != bytes_of(entry["maker"], MAKER_SIZE).rstrip(b"\0") or
                car.model_id != entry["model_id"] or
                car.visual_model_id != entry["visual_model_id"] or
                car.horsepower != entry["horsepower"] or
                car.engine_cc != entry["engine_cc"] or
                car.drive != entry["drive"] or
                car.mission != entry["mission"] or
                car.flags != entry["flags"] or
                not close(car.tire_front, entry["tire_front"]) or
                not close(car.tire_rear, entry["tire_rear"]) or
                car.maker_id != entry["maker_id"]):
            mismatches += 1
            if mismatches <= 3:
                failures.append("record %d (%s) differs" %
                                (index, entry["model"]))
    if mismatches:
        failures.append("%d/%d records differ" % (mismatches, len(entries)))
    else:
        print("  catalog: %d records round-trip, %d bytes" %
              (len(entries), len(blob)))

    index = lib.r6_car_catalog_find_model(cars, len(entries), b"PLC_928GT")
    by_id = lib.r6_car_catalog_find_id(cars, len(entries), 120)
    if index < 0 or by_id != index:
        failures.append("find model/id failed: %d vs %d" % (index, by_id))
    elif cars[index].horsepower != 330 or \
            text(cars[index].maker) != "PORSCHE":
        failures.append("PLC_928GT fields wrong: %d hp, %s" %
                        (cars[index].horsepower, text(cars[index].maker)))
    else:
        print("  PLC_928GT: index %d, model id 120, 330 hp, PORSCHE" % index)

    mapped_count = lib.r6_car_catalog_character_count(blob, len(blob))
    if mapped_count != len(mapped):
        failures.append("character count %d, expected %d" %
                        (mapped_count, len(mapped)))
    for car, model in (("CRC_928GT_Masaki", "PLC_928GT"),
                       ("CRC_AP2_Yuji1st", "PLC_AP2"),
                       ("CRC_R997_Ishida", "PLC_R997")):
        found = lib.r6_car_catalog_find_character(blob, len(blob),
                                                  car.encode("ascii"))
        expected = lib.r6_car_catalog_find_model(cars, len(entries),
                                                 model.encode("ascii"))
        if found < 0 or found != expected:
            failures.append("%s mapped to %d, expected %d" %
                            (car, found, expected))
    if lib.r6_car_catalog_find_character(blob, len(blob),
                                         b"CRC_NOPE") != -1:
        failures.append("unknown character matched")
    if lib.r6_car_catalog_find_character(blob, len(blob),
                                         b"CRC_DUMMY01") != -1:
        failures.append("dummy character matched")
    if mapped_count == len(mapped):
        print("  characters: %d mappings, CRC_928GT_Masaki -> PLC_928GT" %
              mapped_count)

    legacy = bytearray(car_catalog.pack(entries, []))
    legacy[8:12] = struct.pack("<I", 1)
    legacy = bytes(legacy)
    if lib.r6_car_catalog_character_count(legacy, len(legacy)) != 0:
        failures.append("version-1 catalog has mappings")
    maps_bad = bytearray(blob)
    maps_bad[20:24] = struct.pack("<I", 0xffff)
    if lib.r6_car_catalog_character_count(bytes(maps_bad),
                                          len(maps_bad)) != -1:
        failures.append("bad mapping count accepted")

    if lib.r6_car_catalog_find_model(cars, len(entries), b"PLC_NOPE") != -1:
        failures.append("unknown model matched")
    if lib.r6_car_catalog_find_id(cars, len(entries), 60000) != -1:
        failures.append("unknown model id matched")

    if lib.r6_car_catalog_parse(blob[:-1], len(blob) - 1, cars, len(entries),
                                ctypes.byref(count)) != R6_ERR_FORMAT:
        failures.append("truncated catalog accepted")
    bad = b"BAD!" + blob[4:]
    if lib.r6_car_catalog_parse(bad, len(bad), cars, len(entries),
                                ctypes.byref(count)) != R6_ERR_FORMAT:
        failures.append("bad magic accepted")
    bad = blob[:16] + b"\x77\x00\x00\x00" + blob[20:]
    if lib.r6_car_catalog_parse(bad, len(bad), cars, len(entries),
                                ctypes.byref(count)) != R6_ERR_FORMAT:
        failures.append("bad record size accepted")
    rc = lib.r6_car_catalog_parse(blob, len(blob), cars, len(entries) - 1,
                                  ctypes.byref(count))
    if rc != R6_ERR_BUFFER or count.value != len(entries):
        failures.append("short capacity rc=%d count=%d" %
                        (rc, count.value))
    if lib.r6_car_catalog_parse(b"", 0, cars, len(entries),
                                ctypes.byref(count)) != R6_ERR_FORMAT:
        failures.append("empty buffer accepted")

    if failures:
        for item in failures:
            print("FAIL %s" % item)
        return 1
    print("all car catalog checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
