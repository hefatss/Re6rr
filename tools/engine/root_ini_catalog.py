r"""Pack shipped root INI section/key/value facts.

    python tools/engine/root_ini_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/root_ini.r6ini

Paths, section names, keys, values and `;` comment lines are copied verbatim.
Device, card and online behavior is not inferred.
"""

import argparse
import glob
import json
import os
import re
import struct

MAGIC = b"R6INI\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
FILE = struct.Struct("<10I")
SPAN = struct.Struct("<2I")
KEY = struct.Struct("<4I")
NAMES = ("FFBPlugin.ini", "BanaConfig.ini")
EXPECTED_BYTES = 1039
EXPECTED_KEYS = 41
EXPECTED_COMMENTS = 3
COMMENT = re.compile(r"^;.*$")
SECTION = re.compile(r"^\[[A-Za-z_][A-Za-z0-9_]*\]$")
PAIR = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def collect(dump):
    paths = [os.path.join(dump, name) for name in NAMES]
    if sum(os.path.getsize(path) for path in paths) != EXPECTED_BYTES:
        raise ValueError("unexpected root INI corpus")
    files = []
    keys = []
    comments = []
    for path in paths:
        raw = open(path, "rb").read()
        if raw.count(b"\n") != raw.count(b"\r\n"):
            raise ValueError("unexpected INI line ending: " + path)
        lines = raw.decode("ascii", errors="replace").splitlines()
        sections = [line for line in lines if SECTION.match(line)]
        if len(sections) != 1:
            raise ValueError("bad INI section: " + path)
        file_keys = []
        file_comments = []
        for line in lines:
            if COMMENT.match(line):
                file_comments.append(line)
                continue
            if SECTION.match(line) or not line:
                continue
            match = PAIR.match(line)
            if not match:
                raise ValueError("bad INI pair: " + path)
            key, value = match.groups()
            if any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in key) or \
                    any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in value):
                raise ValueError("non-printable INI token: " + path)
            file_keys.append((key, value))
        if not file_keys:
            raise ValueError("empty INI file: " + path)
        comments.extend(file_comments)
        keys.extend(file_keys)
        files.append((os.path.basename(path), len(raw), len(lines),
                      sections[0], file_keys, file_comments))
    if len(keys) != EXPECTED_KEYS or len(comments) != EXPECTED_COMMENTS:
        raise ValueError("unexpected INI totals")
    return files


def build(files):
    keys = [pair for row in files for pair in row[4]]
    comments = [line for row in files for line in row[5]]
    strings_base = HEADER.size + len(files) * FILE.size + \
        len(keys) * KEY.size + len(comments) * SPAN.size
    strings = bytearray()
    offsets = {}

    def add(value):
        raw = value.encode("ascii")
        found = offsets.get(raw)
        if found is not None:
            return found, len(raw)
        offset = strings_base + len(strings)
        offsets[raw] = offset
        strings.extend(raw + b"\0")
        return offset, len(raw)

    key_spans = bytearray()
    comment_spans = bytearray()
    file_rows = bytearray()
    key_base = 0
    comment_base = 0
    for path, size, lines, section, file_keys, file_comments in files:
        path_span = add(path)
        section_span = add(section)
        file_rows.extend(FILE.pack(path_span[0], path_span[1], size, lines,
                                   section_span[0], section_span[1],
                                   key_base, len(file_keys), comment_base,
                                   len(file_comments)))
        for key, value in file_keys:
            key_span = add(key)
            value_span = add(value)
            key_spans.extend(KEY.pack(key_span[0], key_span[1],
                                      value_span[0], value_span[1]))
        for line in file_comments:
            offset, length = add(line)
            comment_spans.extend(SPAN.pack(offset, length))
        key_base += len(file_keys)
        comment_base += len(file_comments)
    header = HEADER.pack(MAGIC, VERSION, len(files), len(keys),
                         len(strings), EXPECTED_BYTES, len(comments))
    return header + bytes(file_rows) + bytes(key_spans) + \
        bytes(comment_spans) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    files = collect(args.dump)
    blob = build(files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="ascii") as stream:
            json.dump([{"path": row[0], "bytes": row[1], "lines": row[2],
                        "section": row[3], "keys": row[4],
                        "comments": row[5]} for row in files], stream,
                      indent=2)
    print("%s: %d INI files, %d keys, %d comments, %d bytes" %
          (args.out, len(files), sum(len(row[4]) for row in files),
           sum(len(row[5]) for row in files), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
