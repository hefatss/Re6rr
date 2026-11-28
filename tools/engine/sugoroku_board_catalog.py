r"""Pack structural facts from the ghost-expedition sugoroku Lua tables.

    python tools/engine/sugoroku_board_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/sugoroku_board.r6sgr

Category id ranges, page square-type counts, reward-category counts and copied
function names are packed. Board timings, item meanings and gameplay rules are
not inferred.
"""

import argparse
import json
import os
import re
import struct

MAGIC = b"R6SGR\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s8I")
CATEGORY = struct.Struct("<6I")
PAGE = struct.Struct("<16I")
FUNCTION = struct.Struct("<2I")
SOURCE = "data_jp/platform_parameters/lua/ghost_expedition_sugoroku.lua"
SOURCE_SIZE = 19910
CATEGORIES = ("CAT_METER", "CAT_NAME_PLATE", "CAT_NAME_PLATE_FOREIGN",
              "CAT_STAMP", "CAT_CONSUMPTION_ITEM", "CAT_HONOR")
TOKENS = ("START", "NORMAL", "STAMP", "TREASURE_BOX", "ROULETTE", "GOAL",
          "BIG_STAMP")
REWARDS = ("CAT_METER", "CAT_NAME_PLATE", "CAT_NAME_PLATE_FOREIGN",
           "CAT_STAMP", "CAT_CONSUMPTION_ITEM", "CAT_HONOR")
EXPECTED = (6, 7, 14, 6, 115, 361)


def strip_comments(text):
    lines = []
    for line in text.splitlines():
        at = line.find("--")
        lines.append(line if at < 0 else line[:at])
    return "\n".join(lines)


def match_brace(text, start):
    depth = 0
    for at in range(start, len(text)):
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                return at
    raise ValueError("unbalanced table braces")


def children(text, start, end):
    found = []
    at = start
    while at < end:
        opened = text.find("{", at, end)
        if opened < 0:
            break
        closed = match_brace(text, opened)
        found.append(text[opened + 1:closed])
        at = closed + 1
    return found


def table(text, name):
    start = text.index(name + " = {")
    opened = text.index("{", start)
    closed = match_brace(text, opened)
    return text[opened + 1:closed]


def collect(dump):
    path = os.path.join(dump, *SOURCE.split("/"))
    raw = open(path, "rb").read()
    if len(raw) != SOURCE_SIZE:
        raise ValueError("unexpected sugoroku source size: %d" % len(raw))
    text = strip_comments(raw.decode("utf-8-sig"))

    category_rows = []
    for name in CATEGORIES:
        marker = "[" + name + "] = {"
        at = text.index(marker) + len(marker) - 1
        closed = match_brace(text, at)
        groups = children(text, at + 1, closed)
        ids = [int(word) for group in groups
               for word in re.findall(r"\b\d+\b", group)]
        if not groups or not ids:
            raise ValueError("empty category: " + name)
        category_rows.append((name, len(groups), len(ids), min(ids), max(ids)))

    page_rows = []
    stages = children(table(text, "SquareTable"), 0,
                      len(table(text, "SquareTable")))
    for stage_index, stage in enumerate(stages, 1):
        for page_index, page in enumerate(children(stage, 0, len(stage)), 1):
            token_counts = dict.fromkeys(TOKENS, 0)
            reward_counts = dict.fromkeys(REWARDS, 0)
            squares = 0
            for line in page.splitlines():
                parts = [part.strip() for part in line.split(",") if part.strip()]
                if not parts:
                    continue
                squares += 1
                if parts[0] not in token_counts:
                    raise ValueError("unknown square token: " + parts[0])
                token_counts[parts[0]] += 1
                if len(parts) > 1 and parts[1].startswith("CAT_"):
                    if parts[1] not in reward_counts:
                        raise ValueError("unknown reward category: " + parts[1])
                    reward_counts[parts[1]] += 1
            page_rows.append((stage_index, page_index, squares,
                              tuple(token_counts[t] for t in TOKENS),
                              tuple(reward_counts[c] for c in REWARDS)))

    functions = re.findall(r"function\s+([A-Za-z_]\w*)", text)
    totals = (len(category_rows), max(row[0] for row in page_rows),
              len(page_rows), len(functions),
              sum(row[2] for row in category_rows),
              sum(row[2] for row in page_rows))
    if totals != EXPECTED:
        raise ValueError("unexpected sugoroku totals: %r" % (totals,))
    return category_rows, page_rows, functions


def build(collection):
    category_rows, page_rows, functions = collection
    strings_base = (HEADER.size + len(category_rows) * CATEGORY.size +
                    len(page_rows) * PAGE.size +
                    len(functions) * FUNCTION.size)
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

    category_bytes = bytearray()
    for name, groups, ids, minimum, maximum in category_rows:
        offset, length = add(name)
        category_bytes.extend(CATEGORY.pack(offset, length, groups, ids,
                                            minimum, maximum))
    page_bytes = bytearray()
    for stage, page, squares, tokens, rewards in page_rows:
        page_bytes.extend(PAGE.pack(stage, page, squares, *tokens, *rewards))
    function_bytes = bytearray()
    for name in functions:
        offset, length = add(name)
        function_bytes.extend(FUNCTION.pack(offset, length))
    header = HEADER.pack(MAGIC, VERSION, len(category_rows),
                         max(row[0] for row in page_rows), len(page_rows),
                         len(functions), sum(row[2] for row in category_rows),
                         sum(row[2] for row in page_rows), len(strings))
    return header + bytes(category_bytes) + bytes(page_bytes) + \
        bytes(function_bytes) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    collection = collect(args.dump)
    blob = build(collection)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        categories, pages, functions = collection
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"categories": categories,
                       "pages": [{"stage": p[0], "page": p[1],
                                  "squares": p[2], "tokens": p[3],
                                  "rewards": p[4]} for p in pages],
                       "functions": functions}, stream, indent=2)
    print("%s: %d categories, %d pages, %d squares, %d bytes" %
          (args.out, len(collection[0]), len(collection[1]),
           sum(row[2] for row in collection[1]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
