"""Check the C road-name surface classifier against shipped LOADLIST labels."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import course_surface  # noqa: E402
import test_engine  # noqa: E402


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_course_classify_surface.restype = ctypes.c_int
    lib.r6_course_classify_surface.argtypes = [ctypes.c_char_p]

    names = set()
    for path in course_surface.loadlist_files(dump, "FUKUOKA"):
        for _section, _binpath, streams in course_surface.parse_loadlist(path):
            for _offset, _size, label in streams:
                names.add(label)
    assert len(names) >= 500

    cases = sorted(names) + [
        "ROAD_gravel1", "ROAD_grass1", "broad_sand_PATH", "unknown_piece",
        "ROAD_PICE_gravel_PICE_broad1", "PICE_KUSA_ROAD", "",
    ]
    counts = {course_surface.SURFACE_ROAD: 0,
              course_surface.SURFACE_GRASS: 0,
              course_surface.SURFACE_GRAVEL: 0, -1: 0}
    for name in cases:
        want = course_surface.classify(name)
        got = lib.r6_course_classify_surface(name.encode("utf8"))
        assert got == want, (name, got, want)
        counts[want] += 1
    assert lib.r6_course_classify_surface(None) == -1
    assert all(counts[key] for key in counts)
    print("course surface: %d shipped FUKUOKA labels and 7 precedence cases "
          "match the Python classifier (road %d, grass %d, gravel %d, "
          "unknown %d)" % (len(names), counts[0], counts[1], counts[2],
                           counts[-1]))


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
