"""Dump-only shape check for the shipped LibraryColor script."""

import argparse
import os
import re

PATH = "data/car/color/LibraryColor.lua"
BYTES = 178158
LINES = 5147
COLOR_MAX = 250
LIST_LINE = 273
BLOCK_LINES = 19
NUMBER = rb"-?[0-9]+(?:\.[0-9]+)?"
VEC4 = re.compile(rb"^\s*\{\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                  rb")\s*,\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                  rb")\s*,\s*\},\s*--")
SCALAR = re.compile(rb"^\s*(" + NUMBER + rb"),\s*--")


def check(dump):
    path = os.path.join(dump, *PATH.split("/"))
    raw = open(path, "rb").read()
    assert len(raw) == BYTES
    sep = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.split(sep)
    if lines and not lines[-1]:
        lines.pop()
    assert len(lines) == LINES
    assert lines[11].strip().startswith(b"COLOR_MAX\t= 250")
    assert lines[LIST_LINE - 1].strip() == b"ColorList = {"
    names = [line for line in lines[17:LIST_LINE - 2]
             if re.match(rb'^\s*"type[0-9]+",', line)]
    assert len(names) == COLOR_MAX
    for local, line in enumerate(names):
        assert line.strip() == b'"type%d",' % local
    for local in range(COLOR_MAX):
        at = LIST_LINE + local * BLOCK_LINES
        block = lines[at:at + BLOCK_LINES]
        assert len(block) == BLOCK_LINES
        assert re.match(rb'^\s*name\s*=\s*"type%d",' % local, block[1])
        assert block[2].strip() == b"ListVec4 = {"
        assert block[6].strip() == b"},"
        assert block[7].strip() == b"ListFloat = {"
        assert block[12].strip() == b"},"
        assert block[13].strip() == b"ListInt = {"
        assert block[17].strip() == b"},"
        assert b"-- end type%d" % local in block[18]
        assert all(VEC4.match(line) for line in block[3:6])
        assert all(SCALAR.match(line) for line in block[8:12])
        assert all(SCALAR.match(line) for line in block[14:17])
    assert lines[LIST_LINE + COLOR_MAX * BLOCK_LINES].strip() == b"}"
    print("LibraryColor: 178158 bytes, 5147 lines, 250 blocks and 4750 "
          "numeric tokens verified")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    return check(args.dump)



if __name__ == "__main__":
    raise SystemExit(main())
