"""Check the C NTWD/NTLX mip-layout facts against the shipped corpus."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nut_texture  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class Layout(ctypes.Structure):
    _fields_ = [("expected_size", ctypes.c_uint64),
                ("face_size", ctypes.c_uint64),
                ("level0_bytes", ctypes.c_uint64),
                ("declared_levels", ctypes.c_uint32),
                ("available_levels", ctypes.c_uint32),
                ("cube", ctypes.c_uint32)]


def descriptor(entry):
    return test_engine.NtwdTexture(
        header_offset=entry["header"], data_offset=entry["data_offset"],
        data_size=entry["data_size"], flags=entry["flags"],
        width=entry["width"], height=entry["height"],
        faces=entry["levels"], format=entry["format"])


def expected(entry):
    size = nut_texture.expected_size(entry)
    faces = 6 if entry["cube"] else 1
    return (size, size // faces,
            nut_texture.level_size(entry["format"], entry["width"],
                                   entry["height"]),
            entry["levels"], nut_texture.available_levels(entry),
            int(bool(entry["cube"])))


def check(dump, lib):
    lib.r6_nut_layout_facts.restype = ctypes.c_int
    lib.r6_nut_layout_facts.argtypes = [
        ctypes.POINTER(test_engine.NtwdTexture), ctypes.POINTER(Layout)]
    facts = Layout()
    entries = 0
    cubes = 0
    short = []
    for directory, _, files in os.walk(dump):
        for name in files:
            if not name.lower().endswith(".nut"):
                continue
            raw = nut_texture.read_nut(os.path.join(directory, name))
            for entry in nut_texture.parse_entries(raw):
                if entry["container"] != "NTWD" or entry["type"] != 2 or \
                        entry["format_name"] is None:
                    continue
                texture = descriptor(entry)
                assert lib.r6_nut_layout_facts(ctypes.byref(texture),
                                               ctypes.byref(facts)) == R6_OK
                got = (facts.expected_size, facts.face_size,
                       facts.level0_bytes, facts.declared_levels,
                       facts.available_levels, facts.cube)
                assert got == expected(entry), (
                    os.path.relpath(os.path.join(directory, name), dump),
                    entry["index"], got, expected(entry))
                assert facts.expected_size == entry["data_size"] or (
                    facts.available_levels < facts.declared_levels and
                    facts.expected_size >= entry["data_size"])
                if facts.available_levels < facts.declared_levels:
                    short.append((os.path.basename(directory) + "/" + name,
                                  entry["index"], facts.declared_levels,
                                  facts.available_levels))
                cubes += facts.cube
                entries += 1

    assert entries == 50180 and cubes == 228 and len(short) == 3
    assert sorted((row[1], row[2], row[3]) for row in short) == [
        (2, 6, 4), (3, 6, 5), (10, 6, 5)]

    bad = descriptor({"header": 0, "data_offset": 0, "data_size": 16,
                      "flags": 0, "width": 4, "height": 4,
                      "levels": 1, "format": 7})
    assert lib.r6_nut_layout_facts(ctypes.byref(bad),
                                   ctypes.byref(facts)) == R6_ERR_FORMAT
    bad.format = 0
    bad.faces = 0
    assert lib.r6_nut_layout_facts(ctypes.byref(bad),
                                   ctypes.byref(facts)) == R6_ERR_FORMAT
    bad.faces = 1
    bad.width = 0
    assert lib.r6_nut_layout_facts(ctypes.byref(bad),
                                   ctypes.byref(facts)) == R6_ERR_FORMAT
    assert lib.r6_nut_layout_facts(None,
                                   ctypes.byref(facts)) == R6_ERR_ARG
    assert lib.r6_nut_layout_facts(ctypes.byref(bad),
                                   None) == R6_ERR_ARG
    print("NTWD layout: %d shipped type-2 entries, %d cube entries and all "
          "three short-mip rows match nut_texture; bad format, zero levels, "
          "zero width and null inputs rejected" % (entries, cubes))


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
