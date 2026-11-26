"""Check the C Enma simulation reader against enma_sim.json."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import enma_sim_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
GETTER_OFF = 32
HIT_OFF = GETTER_OFF + 6 * 24
CONFIG_OFF = HIT_OFF + 4 * 8
KIND = {"float": 0, "int": 1, "bool": 2}


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in
                ("version", "getter_count", "hit_count", "config_size",
                 "strings_size", "strings_off")]


def configure(lib):
    lib.r6_enma_sim_parse.restype = ctypes.c_int
    lib.r6_enma_sim_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_enma_sim_getter.restype = ctypes.c_int
    lib.r6_enma_sim_getter.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t, BUF,
        ctypes.c_size_t, PU32, PU32, PU32, PU32]
    lib.r6_enma_sim_hit.restype = ctypes.c_int
    lib.r6_enma_sim_hit.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32]
    lib.r6_enma_sim_config.restype = ctypes.c_int
    lib.r6_enma_sim_config.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]


def check(lib):
    configure(lib)
    getters, config = enma_sim_catalog.collect()
    blob = enma_sim_catalog.build(getters, config)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_enma_sim_parse(source, len(blob),
                                 ctypes.byref(header)) == R6_OK
    assert header.version == 1
    assert header.getter_count == 6
    assert header.hit_count == 4
    assert header.config_size == 4096
    assert header.strings_off == CONFIG_OFF + 4096
    assert header.strings_size == len(blob) - header.strings_off

    name = ctypes.create_string_buffer(256)
    export_name = ctypes.create_string_buffer(256)
    first = U32()
    count = U32()
    kind = U32()
    bits = U32()
    expected_hit = 0
    for index, (key, item) in enumerate(getters.items()):
        assert lib.r6_enma_sim_getter(
            source, len(blob), index, name, len(name), export_name,
            len(export_name), ctypes.byref(first), ctypes.byref(count),
            ctypes.byref(kind), ctypes.byref(bits)) == R6_OK
        assert name.value.decode("ascii") == key
        assert export_name.value.decode("ascii") == item["export"]
        assert first.value == expected_hit
        assert count.value == len(item["hits"])
        kind_name = type(item["baseline"]).__name__
        assert kind.value == KIND[kind_name]
        assert bits.value == enma_sim_catalog.bits(item["baseline"],
                                                   kind_name)
        expected_hit += len(item["hits"])

    offset = U32()
    value_bits = U32()
    hit_index = 0
    for key, item in getters.items():
        kind_name = type(item["baseline"]).__name__
        for expected in item["hits"]:
            assert lib.r6_enma_sim_hit(
                source, len(blob), hit_index, ctypes.byref(offset),
                ctypes.byref(value_bits)) == R6_OK
            assert offset.value == expected["offset"]
            assert value_bits.value == enma_sim_catalog.bits(expected["value"],
                                                             kind_name)
            hit_index += 1
    assert hit_index == 4

    out = ctypes.create_string_buffer(4096)
    assert lib.r6_enma_sim_config(
        source, len(blob), out, len(out)) == R6_OK
    assert out.raw[:4096] == config

    assert lib.r6_enma_sim_getter(
        source, len(blob), 6, name, len(name), export_name, len(export_name),
        ctypes.byref(first), ctypes.byref(count), ctypes.byref(kind),
        ctypes.byref(bits)) == R6_ERR_ARG
    assert lib.r6_enma_sim_hit(
        source, len(blob), 4, ctypes.byref(offset),
        ctypes.byref(value_bits)) == R6_ERR_ARG
    assert lib.r6_enma_sim_config(
        source, len(blob), out, 4095) == R6_ERR_BUFFER
    assert lib.r6_enma_sim_parse(source, len(blob) - 1,
                                 ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_sim_parse(source, len(bad),
                                 ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, GETTER_OFF + 8, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_sim_getter(
        source, len(bad), 0, name, len(name), export_name, len(export_name),
        ctypes.byref(first), ctypes.byref(count), ctypes.byref(kind),
        ctypes.byref(bits)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, HIT_OFF, 4096)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_enma_sim_hit(
        source, len(bad), 0, ctypes.byref(offset),
        ctypes.byref(value_bits)) == R6_ERR_FORMAT
    print("Enma sim facts: 6 getters, 4 probe hits and 4096 config bytes "
          "match enma_sim.json; bad blob, index, row and capacity rejected")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
