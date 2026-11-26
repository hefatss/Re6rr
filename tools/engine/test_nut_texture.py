"""Self-check for the shipped NTWD/NTLX container inventory."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nut_texture  # noqa: E402


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def run(dump, failures):
    cutin_dir = os.path.join(dump, "data_jp", "scene", "tex", "sp_cutin")
    cutin = [nut_texture.parse_nut(os.path.join(cutin_dir, name))
             for name in sorted(os.listdir(cutin_dir)) if name.endswith(".nut")]
    check(len(cutin) == 36, "cut-in count", failures)
    check(all(row["container"] == "NTWD" and row["version"] == 2 and
              row["entries"] == 1 and not row["compressed"]
              for row in cutin), "cut-in container headers", failures)
    check(all(row["dimensions"] == (384, 320) and
              row["payload_size"] == 0x1E000 and
              row["descriptor_size"] == 0x50 and row["gidx"] == 0x50 and
              row["payload_offset"] == 0x60 and row["exact"]
              for row in cutin), "cut-in layout", failures)
    data = nut_texture.nut_payload(os.path.join(cutin_dir, "st_sp_cutin_00.nut"))
    check(len(data) == 0x1E000, "cut-in payload length", failures)

    rows = nut_texture.collect(dump)
    ntwd = [row for row in rows if row["container"] == "NTWD"]
    check(len(rows) == 11151 and len(ntwd) == 11008, "container counts",
          failures)
    check(sum(row["compressed"] for row in ntwd) == 5431 and
          len(rows) - len(ntwd) == 143, "gzip and NTLX counts", failures)
    check(all(row["entries"] >= 1 and row["payload_size"] > 0
              for row in ntwd) and
          all(row["gidx"] >= 0x50 for row in ntwd if row["version"] == 2),
          "NTWD header sanity", failures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    failures = []
    run(args.dump, failures)
    if failures:
        for item in failures:
            print("FAIL " + item)
        return 1
    print("11151 .nut files, 11008 NTWD (5431 gzip) / 143 NTLX, "
          "36 cut-in textures: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
