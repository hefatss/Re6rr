"""Build the ordered script sets the game actually loads for one car.

    python tools/engine/contexts.py --dump DIR --car NAME [--model CODE] \
        [--kind tire|position|shader|specification|color|all] [--run]

The paths and their order come from the executable, not from sorted directory
walks. Ghidra evidence is in docs/recon/ghidra_c/carctx/:

  * FUN_140114b00 (tire):
      TireDefine.lua -> TireModelType_<car>.lua -> TireAccessor.lua
  * FUN_1400ff3f0 (position):
      getTirePos_<car>.lua -> CarHightDown_<model>.lua (conditional)
  * FUN_14010b110 (shader):
      <model>_ShaderParameter.lua -> ShaderAccessor.lua
  * FUN_1400c8330 (colour):
      LibraryColor.lua, or <dir>/<car>_DefaultColor.lua, or
      playerCar/<car>_CustomColor.lua, selected by file type.

The car name and the model code are different namespaces: the position and
tire files use the car name, while shader/specification/hight-down files use
model codes such as PLC_928GT. Pass --model when you know it.

`sim:` prefixes on the strings in the exe are the game's virtual filesystem;
the platform layer maps them to `data/` on disk.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

BOOTSTRAP = os.path.join("data", "car", "tire", "script", "TireDefine.lua")


def _existing(dump, relative):
    path = os.path.join(dump, relative.replace("/", os.sep))
    return path if os.path.exists(path) else None


def context(dump, car, model=None, kind="all"):
    """Return (kind, ordered absolute paths) for each requested set."""
    model = model or car
    tire = [
        "data/car/tire/script/TireDefine.lua",
        "data/car/tire/model_type/TireModelType_%s.lua" % car,
        "data/car/tire/script/TireAccessor.lua",
    ]
    position = [
        "data/car/position/pos/getTirePos_%s.lua" % car,
        "data/car/position/hightDown/CarHightDown_%s.lua" % model,
        "data/car/position/StroboLightOnOffParameter.lua",
    ]
    shader = [
        "data/car/shader/parameter/%s_ShaderParameter.lua" % model,
        "data/car/shader/script/ShaderAccessor.lua",
    ]
    specification = ["data/car/specification/%s_Specification.lua" % model]
    color = [
        "data/car/color/LibraryColor.lua",
        "data/car/color/ColorCommonParamerter.lua",
        "data/car/color/NeonColor.lua",
    ]

    sets = {
        "tire": tire,
        "position": position,
        "shader": shader,
        "specification": specification,
        "color": color,
    }
    if kind != "all":
        sets = {kind: sets[kind]}
    # TireDefine must come before every other set: position, shader and
    # specification scripts read its constants at load time.
    order = ["tire", "position", "shader", "specification", "color"]
    result = []
    for name in order:
        if name not in sets:
            continue
        paths = []
        for relative in sets[name]:
            path = _existing(dump, relative)
            if path:
                paths.append(path)
        result.append((name, paths))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                     r"D:\Games\W6W-05"))
    ap.add_argument("--car", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--kind", default="all",
                    choices=["all", "tire", "position", "shader",
                             "specification", "color"])
    ap.add_argument("--run", action="store_true",
                    help="load the bundle through the C engine and query it")
    ap.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                  "r6_engine.dll"))
    args = ap.parse_args()

    sets = context(args.dump, args.car, args.model, args.kind)
    for name, paths in sets:
        print("%s: %d scripts" % (name, len(paths)))
        for path in paths:
            print("  " + os.path.relpath(path, args.dump))
    if not args.run:
        return 0

    from test_engine import Engine, R6_OK  # noqa: E402

    paths = []
    for _name, group in sets:
        paths.extend(group)
    engine = Engine(args.dll, args.dump)
    try:
        engine.setting_const()
        rc, message = engine.context(paths)
        if rc != R6_OK:
            print("LOAD FAILED rc=%d %s" % (rc, message))
            return 1
        print("loaded %d scripts" % len(paths))
        rc, vec = engine.vec3_key("GetTirePos", args.car, 0)
        print("GetTirePos(%r, 0) rc=%d = %r" % (args.car, rc, vec))
        return 0 if rc == R6_OK else 1
    finally:
        engine.close()


if __name__ == "__main__":
    sys.exit(main())
