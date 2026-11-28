r"""Pack shipped tire/lamp/strobo position row shapes.

    python tools/engine/tire_lamp_pos_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/tire_lamp_pos.r6tlp

Paths, embedded car ids, section keys and lines, scalar count tokens and
verbatim vector token bytes are copied. CP932 comments, axis meanings and
lighting roles stay unparsed.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6TLP\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s11I")
FILE = struct.Struct("<8I")
SECTION = struct.Struct("<8I")
ROW = struct.Struct("<4I")
PATTERN = "data/car/position/pos/getTirePos_*.lua"
EXPECTED_FILES = 255
EXPECTED_BYTES = 22041850
ASSIGN = re.compile(rb"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
NUMBER = rb"-?[0-9]+(?:\.[0-9]+)?"
VEC = re.compile(rb"^\s*\{\s*(" + NUMBER + rb")\s*,\s*(" + NUMBER +
                 rb")\s*,\s*(" + NUMBER + rb")\s*,\s*\},")
IDENT = re.compile(rb"^[A-Za-z0-9_]+$")


def collect(dump):
    paths = sorted(glob.glob(os.path.join(dump, *PATTERN.split("/"))))
    if len(paths) != EXPECTED_FILES or \
            sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected tire position corpus")
    files = []
    sections = []
    rows = []
    lists = 0
    scalars = 0
    for path in paths:
        raw = open(path, "rb").read()
        sep = b"\r\n" if b"\r\n" in raw else b"\n"
        lines = raw.split(sep)
        if lines and not lines[-1]:
            lines.pop()
        car_id = None
        at = 0
        section_base = len(sections)
        while at < len(lines):
            match = ASSIGN.match(lines[at])
            if not match:
                at += 1
                continue
            key, value = match.group(1), match.group(2)
            if value.endswith(b","):
                value = value[:-1].rstrip()
            if key == b"name":
                text = re.fullmatch(rb'"([^"]*)"', value)
                if not text or car_id is not None:
                    raise ValueError("unexpected car id: " + path)
                car_id = text.group(1)
                at += 1
                continue
            if key == b"CarDataPosList" or key == b"DEBUG_CODE":
                at += 1
                continue
            if not value:
                if at + 1 >= len(lines) or lines[at + 1].strip() != b"{":
                    raise ValueError("missing vector opener: " + path)
                stop = at + 2
                base = len(rows)
                while stop < len(lines) and lines[stop].strip() != b"},":
                    vec = VEC.match(lines[stop])
                    if not vec:
                        raise ValueError("unexpected vector row: " + path)
                    rows.append((stop + 1, tuple(
                        vec.group(n).strip() for n in (1, 2, 3))))
                    stop += 1
                if stop >= len(lines):
                    raise ValueError("missing vector closer: " + path)
                if b"Num" in key:
                    raise ValueError("vector count key: " + path)
                sections.append((key, at + 1, 0, b"", base, len(rows) - base))
                lists += 1
                at = stop + 1
                continue
            if not re.fullmatch(NUMBER, value) or b"Num" not in key:
                raise ValueError("unexpected scalar: " + path)
            sections.append((key, at + 1, 1, value.strip(), len(rows), 0))
            scalars += 1
            at += 1
        if car_id is None or not IDENT.match(car_id):
            raise ValueError("missing car id: " + path)
        files.append((os.path.basename(path), car_id, len(raw), len(lines),
                      section_base, len(sections) - section_base))
    if lists != 14775 or scalars != 14022 or len(rows) != 23759:
        raise ValueError("unexpected tire position shape totals")
    return files, sections, rows


def build(files, sections, rows):
    base = (HEADER.size + len(files) * FILE.size +
            len(sections) * SECTION.size + len(rows) * ROW.size)
    strings = bytearray()
    offsets = {}

    def add(value):
        found = offsets.get(value)
        if found is not None:
            return found
        offset = base + len(strings)
        offsets[value] = offset
        strings.extend(value + b"\0")
        return offset

    file_rows = bytearray()
    for name, car_id, size, lines, section_base, count in files:
        raw_name = name.encode("ascii")
        name_span = add(raw_name)
        car_span = add(car_id)
        file_rows.extend(FILE.pack(name_span, len(raw_name), car_span,
                                   len(car_id), size, lines,
                                   section_base, count))
    section_rows = bytearray()
    for key, line, kind, value, row_base, row_count in sections:
        key_span = add(key)
        value_span = add(value) if value else 0
        section_rows.extend(SECTION.pack(key_span, len(key), line, kind,
                                         value_span, len(value),
                                         row_base, row_count))
    vector_rows = bytearray()
    for line, tokens in rows:
        spans = [add(token) for token in tokens]
        vector_rows.extend(ROW.pack(line, spans[0], spans[1], spans[2]))
    header = HEADER.pack(
        MAGIC, VERSION, len(files), len(sections),
        sum(section[2] == 0 for section in sections),
        sum(section[2] == 1 for section in sections),
        len(rows), len(rows) * 3,
        sum(entry[3] for entry in files), EXPECTED_BYTES, len(strings), 0)
    return header + bytes(file_rows) + bytes(section_rows) + \
        bytes(vector_rows) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files, sections, rows = collect(args.dump)
    blob = build(files, sections, rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump({"files": [[a, b.decode("ascii"), c, d, e, f]
                                 for a, b, c, d, e, f in files],
                       "sections": [[a.decode("ascii"), b, c,
                                     d.decode("ascii"), e, f]
                                    for a, b, c, d, e, f in sections],
                       "rows": [[a, [t.decode("ascii") for t in b]]
                                for a, b in rows]}, stream, indent=2)
    print("%s: 255 files, 28797 sections, 23759 rows, 71277 tokens, "
          "%d bytes" % (args.out, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
