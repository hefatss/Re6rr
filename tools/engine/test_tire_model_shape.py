"""Dump-only shape check for shipped tire model type scripts.

No blob is packed and no engine API is exercised. The check records the
shipped section/line layout so later readers start from grounded facts.
"""

import argparse
import glob
import os
import re

PATTERN = "data/car/tire/model_type/TireModelType_*.lua"
EXPECTED_FILES = 240
EXPECTED_BYTES = 165906
LIST_KEYS = (b"inc_normal", b"inc_size_up", b"wheel_scale", b"tire_width")
SCALAR_KEYS = (b"tire_outside_front", b"tire_outside_rear",
               b"wheel_default", b"wheel_color")
OUTLIER = "TireModelType_PLC_VMG.lua"
QUOTED = re.compile(rb'^"([A-Za-z0-9_]+)",\s*(?:--.*)?$')
BARE = re.compile(rb"^([A-Za-z0-9_.]+),\s*(?:--.*)?$")
NUMBER = re.compile(rb"^[0-9]+(?:\.[0-9]+)?$")


def check(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/"))))
    assert len(paths) == EXPECTED_FILES
    assert sum(os.path.getsize(path) for path in paths) == EXPECTED_BYTES
    regular = 0
    for path in paths:
        raw = open(path, "rb").read()
        sep = b"\r\n" if b"\r\n" in raw else b"\n"
        lines = raw.split(sep)
        if lines and not lines[-1]:
            lines.pop()
        if os.path.basename(path) == OUTLIER:
            assert len(lines) in (31, 32)
            assert lines[0].startswith(b"TireInfo = \t--")
            assert lines[1].strip() == b"{"
            regular += 1
            continue
        assert len(lines) == 30, path
        assert lines[0].strip() == b"TireInfo = \t{", path
        assert lines[-1].strip() == b"}", path
        for local, key in enumerate(LIST_KEYS):
            at = 1 + local * 6
            assert lines[at].strip() == key + b" = {", (path, at + 1)
            for line in lines[at + 1:at + 5]:
                token = line.strip()
                if local < 2:
                    assert QUOTED.match(token), (path, token)
                else:
                    assert BARE.match(token), (path, token)
            assert lines[at + 5].strip() == b"},", path
        for index, key in enumerate(SCALAR_KEYS):
            match = re.match(rb"\s*" + key +
                             rb"\s*=\s*(.+?)\s*,--", lines[25 + index])
            assert match, (path, key)
            token = match.group(1)
            if key == b"wheel_default":
                assert re.fullmatch(rb'"[A-Za-z0-9_]+"', token), (path, token)
            else:
                assert NUMBER.match(token), (path, token)
        regular += 1
    print("Tire model types: 240 files, 165906 bytes, 239 regular and 1 "
          "outlier layout; 9 sections per file verified")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    return check(args.dump)


if __name__ == "__main__":
    raise SystemExit(main())
