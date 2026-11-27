"""Check the C NTWD/NTLX file-level header reader against all shipped .nut files."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nut_texture  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class Facts(ctypes.Structure):
    _fields_ = [
        ("container", ctypes.c_uint32),
        ("version", ctypes.c_uint32),
        ("entries", ctypes.c_uint32),
        ("total", ctypes.c_uint64),
        ("payload_size", ctypes.c_uint32),
        ("descriptor_size", ctypes.c_uint32),
        ("packed0", ctypes.c_uint32),
        ("packed1", ctypes.c_uint32),
        ("first_gidx", ctypes.c_uint64),
        ("payload_offset", ctypes.c_uint64),
        ("exact", ctypes.c_uint32),
    ]


def expected(raw):
    version, entries = struct.unpack_from("<HH", raw, 4)
    total = struct.unpack_from("<Q", raw, 0x10)[0]
    payload_size, descriptor_size = struct.unpack_from("<II", raw, 0x18)
    packed0, packed1 = struct.unpack_from("<II", raw, 0x20)
    gidx = struct.unpack_from("<Q", raw, 0x30)[0]
    offset = 0x10 + entries * descriptor_size
    return (
        int.from_bytes(raw[:4], "little"), version, entries, total,
        payload_size, descriptor_size, packed0, packed1, gidx, offset,
        1 if len(raw) == offset + entries * payload_size else 0,
    )


def fields(facts):
    return (
        facts.container, facts.version, facts.entries, facts.total,
        facts.payload_size, facts.descriptor_size, facts.packed0,
        facts.packed1, facts.first_gidx, facts.payload_offset, facts.exact,
    )


def check_corpus(dump, lib):
    lib.r6_nut_container_facts.restype = ctypes.c_int
    lib.r6_nut_container_facts.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.POINTER(Facts)]
    facts = Facts()
    files = 0
    ntwd = 0
    exact = 0
    for directory, _, names in os.walk(dump):
        for name in names:
            if not name.lower().endswith(".nut"):
                continue
            path = os.path.join(directory, name)
            raw = nut_texture.read_nut(path)
            source = ctypes.create_string_buffer(raw, len(raw))
            assert lib.r6_nut_container_facts(
                source, len(raw), ctypes.byref(facts)) == R6_OK, path
            assert fields(facts) == expected(raw), path
            files += 1
            ntwd += raw[:4] == nut_texture.NTWD
            exact += facts.exact
    assert (files, ntwd, exact) == (11151, 11008, 9599)
    print("NTWD/NTLX header: %d files (%d NTWD, %d NTLX), %d exact layouts, "
          "all 11 fields match nut_texture.py" % (files, ntwd, files - ntwd,
                                                  exact))


def synthetic(size=0x80):
    raw = bytearray(size)
    raw[0:4] = b"NTWD"
    struct.pack_into("<HH", raw, 4, 2, 1)
    struct.pack_into("<QII", raw, 0x10, 5, 16, 0x50)
    struct.pack_into("<II", raw, 0x20, 0x1111, 0x2222)
    struct.pack_into("<Q", raw, 0x30, 0x50)
    return bytes(raw)


def check_negative(lib):
    lib.r6_nut_container_facts.restype = ctypes.c_int
    lib.r6_nut_container_facts.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.POINTER(Facts)]
    facts = Facts()
    raw = synthetic()
    source = ctypes.create_string_buffer(raw, len(raw))
    assert lib.r6_nut_container_facts(
        source, len(raw), ctypes.byref(facts)) == R6_OK
    assert fields(facts) == expected(raw)
    assert facts.exact == 0

    exact_raw = synthetic(0x70)
    source = ctypes.create_string_buffer(exact_raw, len(exact_raw))
    assert lib.r6_nut_container_facts(
        source, len(exact_raw), ctypes.byref(facts)) == R6_OK
    assert fields(facts) == expected(exact_raw)
    assert facts.exact == 1

    bad = bytearray(raw)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nut_container_facts(
        source, len(bad), ctypes.byref(facts)) == R6_ERR_FORMAT
    for offset, value in ((4, 3), (6, 0), (0x1c, 0x40)):
        bad = bytearray(raw)
        if offset == 4 or offset == 6:
            struct.pack_into("<H", bad, offset, value)
        else:
            struct.pack_into("<I", bad, offset, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_nut_container_facts(
            source, len(bad), ctypes.byref(facts)) == R6_ERR_FORMAT
    source = ctypes.create_string_buffer(raw, len(raw))
    assert lib.r6_nut_container_facts(
        source, 0x37, ctypes.byref(facts)) == R6_ERR_FORMAT
    assert lib.r6_nut_container_facts(
        None, len(raw), ctypes.byref(facts)) == R6_ERR_ARG
    assert lib.r6_nut_container_facts(
        source, len(raw), None) == R6_ERR_ARG
    print("NTWD/NTLX header negatives: bad magic, short blob, version 3, "
          "zero entries, small descriptor, null input/output rejected")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check_corpus(args.dump, lib)
    check_negative(lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
