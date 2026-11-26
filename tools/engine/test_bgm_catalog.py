"""Check the packed BGM table against the C reader."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import bgm_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_NOT_FOUND = -7


class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32),
                ("count", ctypes.c_uint32),
                ("id_first", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


class Record(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint16), ("flags", ctypes.c_uint16),
                ("name_off", ctypes.c_uint32), ("path_off", ctypes.c_uint32)]


def configure(lib):
    lib.r6_bgm_parse.restype = ctypes.c_int
    lib.r6_bgm_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.POINTER(Header)]
    lib.r6_bgm_find_id.restype = ctypes.c_int
    lib.r6_bgm_find_id.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.c_uint16, ctypes.POINTER(Record)]
    lib.r6_bgm_find_name.restype = ctypes.c_int
    lib.r6_bgm_find_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_char_p, ctypes.POINTER(Record)]
    lib.r6_bgm_string.restype = ctypes.c_char_p
    lib.r6_bgm_string.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.c_uint32]


def check(dump):
    rows = bgm_catalog.collect(dump)
    blob = bgm_catalog.build(rows)
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    buffer = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_bgm_parse(buffer, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.count, header.id_first) == (1, 142, 0)
    assert header.strings_off == 32 + 142 * 12
    assert header.strings_off + header.strings_size == len(blob)

    for want in rows:
        got = Record()
        assert lib.r6_bgm_find_id(buffer, len(blob), want["id"],
                                  ctypes.byref(got)) == R6_OK
        flags = 0
        if want["id"] == audio_events.BGM_NO_SOUND:
            flags |= bgm_catalog.FLAG_STOP
        if want["id"] == audio_events.BGM_RANDOM:
            flags |= bgm_catalog.FLAG_RANDOM
        assert (got.id, got.flags) == (want["id"], flags)
        assert lib.r6_bgm_string(buffer, len(blob), got.name_off) == \
            want["name"].encode("utf8")
        assert lib.r6_bgm_string(buffer, len(blob), got.path_off) == \
            want["path"].encode("utf8")

        found = Record()
        rc = lib.r6_bgm_find_name(buffer, len(blob),
                                  want["name"].encode("utf8"),
                                  ctypes.byref(found))
        assert rc == R6_OK
        assert found.id == audio_events.bgm_by_name(rows, want["name"])

    named = Record()
    assert lib.r6_bgm_find_name(buffer, len(blob), b"SYSTEMBGM_STORY",
                                ctypes.byref(named)) == R6_OK
    assert named.id == 1
    assert lib.r6_bgm_find_name(buffer, len(blob), b"not shipped",
                                ctypes.byref(named)) == R6_ERR_NOT_FOUND
    assert lib.r6_bgm_find_id(buffer, len(blob), 200,
                              ctypes.byref(named)) == R6_ERR_NOT_FOUND
    assert lib.r6_bgm_find_name(buffer, len(blob), b"",
                                ctypes.byref(named)) == R6_ERR_ARG

    bad = bytearray(blob)
    bad[0] = 0
    assert lib.r6_bgm_parse(ctypes.create_string_buffer(bytes(bad), len(bad)),
                            len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 8, 2)
    assert lib.r6_bgm_parse(ctypes.create_string_buffer(bytes(bad), len(bad)),
                            len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_bgm_parse(buffer, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 32 + 8, 0)
    assert lib.r6_bgm_find_id(ctypes.create_string_buffer(bytes(bad),
                                                          len(bad)), len(bad),
                              0, ctypes.byref(named)) == R6_ERR_FORMAT
    print("BGM catalog: %d ids, %d bytes; names/paths/flags and lookups match "
          "wmn6r.exe; bad magic/version/truncation/offset: OK" %
          (len(rows), len(blob)))


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
