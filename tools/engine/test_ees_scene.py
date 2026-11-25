"""Self-check for the EventScene2 .EES container parser."""

import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ees_scene  # noqa: E402


def read(dump, name):
    path = os.path.join(dump, ees_scene.SCENE_DIR, *name.split("/"))
    with open(path, "rb") as stream:
        return stream.read()


def check(dump):
    cam = ees_scene.parse_ees(read(
        dump, "ESeries_001/FrontEvent/CamData.EES"))
    assert cam["kind"] == "cam" and cam["version"] == 0x2712
    assert cam["file_size"] == 110584 and cam["count"] == 255
    assert cam["header_size"] == 0x1a8
    assert [(item["name"], item["offset"], item["size"])
            for item in cam["arrays"]] == [
        ("camera_info", 0x1a8, 20400),
        ("camera_data", 0x1a8 + 20400, 89760),
    ]
    assert [item["stride"] for item in cam["arrays"]] == [0x50, 0x160]
    assert all(item["count"] == cam["count"] for item in cam["arrays"])

    car = ees_scene.parse_ees(read(
        dump, "ESeries_001/FrontEvent/CarData0.EES"))
    assert car["kind"] == "car" and car["file_size"] == 7387644
    assert car["count"] == car["effect_count"] == 10800
    assert car["header_size"] == 0x1bc
    assert [item["stride"] for item in car["arrays"]] == \
        [0x180, 0xa0, 0x8c]
    assert sum(item["size"] for item in car["arrays"]) + car["header_size"] \
        == car["file_size"]

    data = ees_scene.collect(dump)
    files = data["files"]
    assert len(files) == 1129
    assert sum(item["kind"] == "cam" for item in files.values()) == 720
    assert sum(item["kind"] == "car" for item in files.values()) == 409
    assert sum(item["version"] == 0x2713 for item in files.values()) == 325
    sizes = {}
    for item in files.values():
        key = (item["kind"], item["header_size"])
        sizes[key] = sizes.get(key, 0) + 1
    assert sizes == {
        ("cam", 0x1a8): 429, ("cam", 0x1b0): 291,
        ("car", 0x1bc): 243, ("car", 0x1c8): 166,
    }
    assert all(item["file_size"] == os.path.getsize(os.path.join(
        dump, ees_scene.SCENE_DIR, *name.split("/")))
        for name, item in files.items())

    with tempfile.TemporaryDirectory() as directory:
        output = os.path.join(directory, "cam_info.bin")
        header, array = ees_scene.extract(
            dump, "ESeries_001/FrontEvent/CamData.EES", 0, output)
        assert len(open(output, "rb").read()) == array["size"] == \
            header["count"] * 0x50
    print("  1129 .EES files, 720 cam / 409 car, one array extract round-trip: all scene checks passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
