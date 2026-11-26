"""Self-check for shipped NTWD/NTLX layout, pixel formats and CPU decode."""

import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nut_texture  # noqa: E402


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def load(dump, relative):
    return nut_texture.read_nut(os.path.join(dump, *relative.split("/")))


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

    ntlx = [row for row in rows if row["container"] == "NTLX"]
    check(len(ntlx) == 143 and all(row["version"] == 1 and
                                   row["compressed"] and
                                   row["descriptor_size"] == 0x50 and
                                   row["gidx"] == 0 for row in ntlx),
          "NTLX headers", failures)
    check(sum(row["exact"] for row in ntlx) == 140 and
          {row["bytes_per_pixel"] for row in ntlx} == {1, 4},
          "NTLX layouts", failures)
    logo_path = os.path.join(dump, "data_jp", "texture", "logo_s",
                             "cmn_car_logo_s100.nut")
    logo = nut_texture.parse_nut(logo_path)
    check(logo["total"] == 0x8050 and logo["payload_size"] == 0x8000 and
          logo["dimensions"] == (256, 128) and
          logo["payload_offset"] == 0x60 and logo["exact"],
          "NTLX single entry", failures)
    check(len(nut_texture.nut_payload(logo_path)) == 0x8000,
          "NTLX payload length", failures)


def check_pixels(dump, failures):
    flame = load(dump, "data/car/numberPlate/flame/flame_illumination1_c1.nut")
    entries = nut_texture.parse_entries(flame)
    check([entry["format_name"] for entry in entries[:2]] == ["BC3", "BC1"],
          "flame formats", failures)
    check(entries[0]["levels"] == 1 and entries[0]["width"] == 256 and
          entries[0]["height"] == 128 and entries[0]["data_size"] == 0x8000,
          "flame BC3 header", failures)
    rgba = nut_texture.decode_entry(flame, entries[0])
    alpha = rgba[3::4]
    check(len(rgba) == 256 * 128 * 4 and alpha[0] == 255 and
          alpha[64 * 256 + 128] == 0 and len(set(alpha)) > 1,
          "BC3 alpha decode", failures)

    blend = load(dump, "data/car/blend/blend_system.nut")
    entry = nut_texture.parse_entries(blend)[0]
    check(entry["format_name"] == "A8R8G8B8" and
          entry["width"] == 128 and entry["height"] == 128,
          "A8R8G8B8 header", failures)
    rgba = nut_texture.decode_entry(blend, entry)
    payload = nut_texture.nut_payload(
        os.path.join(dump, "data", "car", "blend", "blend_system.nut"))
    check(rgba[:4] == bytes((payload[2], payload[1], payload[0], payload[3])),
          "A8R8G8B8 channel order", failures)

    bc2 = load(dump, "data/course/stage/A_FUKUOKA_DAY_NML/FUKUOKA/model/nut/"
                     "FUKUOKA_DAY_NML_Tex1.nut")
    entry = nut_texture.parse_entries(bc2)[0]
    check(entry["format_name"] == "BC2" and entry["levels"] == 3,
          "BC2 header", failures)
    rgba = nut_texture.decode_entry(bc2, entry)
    check(len(rgba) == entry["width"] * entry["height"] * 4 and
          len(set(rgba[3::4])) > 1, "BC2 decode", failures)

    bc1 = load(dump, "data/car/car_data/otherCar/OTH_NZE121.nut")
    entry = nut_texture.parse_entries(bc1)[0]
    check(entry["format_name"] == "BC1" and entry["levels"] == 1,
          "BC1 header", failures)
    rgba = nut_texture.decode_entry(bc1, entry)
    check(len(rgba) == 512 * 512 * 4 and len(set(rgba[::4])) > 1 and
          rgba[3::4] == b"\xff" * (512 * 512), "BC1 decode", failures)

    argb = load(dump, "data_jp/flash/DRIVE/ghost_battle/"
                      "B073_02_01_DRESSUP_SEL00.nut")
    entries = [item for item in nut_texture.parse_entries(argb)
               if item["format_name"] == "ARGB8"]
    check(len(entries) == 1 and entries[0]["index"] == 12 and
          entries[0]["width"] == 336 and entries[0]["height"] == 336 and
          entries[0]["levels"] == 1 and
          nut_texture.expected_size(entries[0]) == 336 * 336 * 4,
          "ARGB8 header", failures)
    rgba = nut_texture.decode_entry(argb, entries[0])
    alpha = rgba[3::4]
    center = rgba[(168 * 336 + 168) * 4:(168 * 336 + 168) * 4 + 4]
    check(alpha[0] == 0 and alpha[10] == 3 and
          len(set(alpha)) > 1 and center == bytes((0x24, 0x1a, 0, 255)),
          "ARGB8 alpha corner and channel order", failures)


def check_formats(dump, failures):
    stats = collections.Counter()
    bad = []
    for directory, _, files in os.walk(dump):
        for name in files:
            if not name.lower().endswith(".nut"):
                continue
            raw = nut_texture.read_nut(os.path.join(directory, name))
            for entry in nut_texture.parse_entries(raw):
                if entry["container"] != "NTWD" or entry["type"] != 2:
                    continue
                if entry["format_name"] is None:
                    stats["unknown"] += 1
                elif nut_texture.expected_size(entry) == entry["data_size"]:
                    stats["match"] += 1
                elif (nut_texture.available_levels(entry) < entry["levels"] and
                      nut_texture.expected_size(entry) >= entry["data_size"]):
                    stats["short-mips"] += 1
                else:
                    stats["bad"] += 1
                    if len(bad) < 5:
                        bad.append((os.path.relpath(os.path.join(directory,
                                                                 name), dump),
                                    entry["index"], entry["format_name"],
                                    entry["data_size"]))
    check(stats["match"] == 50177 and stats["short-mips"] == 3 and
          stats["unknown"] == 0 and stats["bad"] == 0,
          "payload size model %s %s" % (dict(stats), bad), failures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    failures = []
    run(args.dump, failures)
    check_pixels(args.dump, failures)
    check_formats(args.dump, failures)
    if failures:
        for item in failures:
            print("FAIL " + item)
        return 1
    print("11151 .nut files, 11008 NTWD (5431 gzip) / 143 NTLX "
          "(140 exact), 36 cut-ins, 50177 payload sizes, 5 CPU formats: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
