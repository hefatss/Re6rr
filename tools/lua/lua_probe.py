"""Load the WMMT6RR data scripts and exercise the native -> Lua call protocol.

    python tools/lua/lua_probe.py --dump D:\\Games\\W6W-05
    python tools/lua/lua_probe.py --dump DIR --scripts PATH --query GetTirePos NAME 0 --vec3

With no --scripts, every .lua under DUMP/data is loaded in sorted path order.
That order matters: the data scripts overwrite globals such as ColorMax and
CarDataPosList, so a real engine loads only the script set for the current
context (one car's position file, one course's section file, ...).
"""

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from lua_host import LuaHost, LuaError, LUA_TNIL  # noqa: E402

TIRE_WIDTHS = (155, 165, 175, 185, 195, 205, 215, 225, 235, 245, 255, 265,
               275, 285, 295, 305, 315, 325, 335, 345, 355)
WHEEL_SIZES = range(13, 23)

# setting_default.lua says SettingConst is defined by the program, not by data.
SETTING_CONST = {
    "Locale": {"Japan": 0, "Usa": 1},
    "Language": {"Japanese": 0, "English": 1},
    "Difficult": {"Normal": 1},
    "NetworkMode": {"Network_Enable": 1},
    "NetworkID": {"NetworkID_2": 2},
    "ForceFeedBackLevel": {"TorqueLevel3": 3},
    "State": {"Enable": 1},
}


def script_paths(dump):
    return sorted(glob.glob(os.path.join(dump, "data", "**", "*.lua"),
                            recursive=True))


def native_names(bindings, reg_table):
    names = []
    if bindings and os.path.exists(bindings):
        names.extend(json.load(open(bindings, encoding="utf8")))
    if reg_table and os.path.exists(reg_table):
        data = json.load(open(reg_table, encoding="utf8"))
        for table in data.get("reg", []):
            for entry in table.get("entries", []):
                name = entry[0] if isinstance(entry, (list, tuple)) else None
                if isinstance(name, str) and name.isidentifier():
                    names.append(name)
    return sorted(set(names))


def install_native_globals(host, names):
    """Supply globals the data scripts expect from the native side.

    Values for the wheel/tire constants and SettingConst are placeholders:
    only their existence is needed to run the scripts. Recover the real values
    from wmn6r.exe before using the host as a gameplay reference.
    """
    host.set_table("SettingConst", SETTING_CONST)
    for width in TIRE_WIDTHS:
        host.set_number("TIRE_WIDTH_SCALE_%d" % width, 1.0)
    for size in WHEEL_SIZES:
        host.set_number("WHEEL_SCALE_INC_%d" % size, 1.0)
    for name in names:
        if host.global_type(name) == LUA_TNIL:
            host.set_function(name, lambda *args: 0)


def parse_arg(text):
    try:
        return int(text, 0)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                     r"D:\Games\W6W-05"))
    ap.add_argument("--lua", default=None, help="path to lua5.1.dll")
    ap.add_argument("--scripts", nargs="+", help="load only these scripts")
    ap.add_argument("--query", nargs="+", action="append", default=[],
                    metavar=("NAME", "ARG"), help="call a Lua global")
    ap.add_argument("--vec3", action="store_true",
                    help="queries return three numbers, like FUN_1400d20d0")
    ap.add_argument("--bindings", default=os.path.join(ROOT, "docs", "recon",
                                                       "bindings.json"))
    ap.add_argument("--reg-table", default=os.path.join(ROOT, "docs", "recon",
                                                        "name_tables.json"))
    ap.add_argument("--no-stubs", action="store_true")
    ap.add_argument("--no-track", action="store_true")
    args = ap.parse_args()

    lua = args.lua or os.environ.get("LUA51_DLL") or os.path.join(
        args.dump, "lua5.1.dll")
    paths = args.scripts or script_paths(args.dump)
    failed = False
    with LuaHost(lua) as host:
        print("lua=%s" % host.lua_path)
        if not args.no_stubs:
            install_native_globals(
                host, native_names(args.bindings, args.reg_table))
        if not args.no_track:
            host.track_missing_globals()
        for path in paths:
            try:
                host.load_file(path)
            except (LuaError, OSError) as exc:
                failed = True
                print("LOAD ERR %s %s" % (path, exc))
        print("scripts=%d" % len(paths))
        if not args.no_track:
            missing = host.missing_globals
            print("missing_globals=%d %s" % (
                len(missing),
                sorted(missing, key=lambda k: -missing[k])[:16]))
        for query in args.query:
            name, raw_args = query[0], query[1:]
            try:
                result = (host.call_vec3(name, *map(parse_arg, raw_args))
                          if args.vec3 else
                          host.call(name, *map(parse_arg, raw_args)))
            except LuaError as exc:
                failed = True
                print("CALL ERR %s(%s) %s" % (
                    name, ", ".join(raw_args), exc))
            else:
                print("CALL %s(%s) = %s" % (name, ", ".join(raw_args), result))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
