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

# data/car/tire/script/TireDefine.lua defines the WHEEL_SCALE_INC_* and
# TIRE_WIDTH_SCALE_* constants, but some scripts read them before that file in
# sorted path order. Load it first so the values are the game's own.
BOOTSTRAP = os.path.join("data", "car", "tire", "script", "TireDefine.lua")

# setting_default.lua says SettingConst is defined by the program, not by data.
# Values come from FUN_140c4db10 (luabind registration of sys::setting enums).
SETTING_CONST = {
    "Locale": {"Japan": 0, "Usa": 1, "China": 2, "Korea": 3, "Euro": 4},
    "Language": {"Japanese": 0, "English": 1},
    "Difficult": {"VeryEasy": 0, "Easy": 1, "Normal": 2, "Hard": 3,
                  "VeryHard": 4},
    "NetworkMode": {"Network_Disable": 0, "Network_Enable": 1,
                    "Disable": 0, "Enable": 1},
    "NetworkID": {"NetworkID_%d" % i: i for i in range(8)},
    "ForceFeedBackLevel": {"Disable": 0, "TorqueLevel2": 1,
                           "TorqueLevel3": 2},
    "State": {"Disable": 0, "Enable": 1},
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

    SettingConst values mirror the enum registration in FUN_140c4db10.
    """
    host.set_table("SettingConst", SETTING_CONST)
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
    ap.add_argument("--no-bootstrap", action="store_true",
                    help="do not preload TireDefine.lua")
    ap.add_argument("--no-track", action="store_true")
    args = ap.parse_args()

    lua = args.lua or os.environ.get("LUA51_DLL") or os.path.join(
        args.dump, "lua5.1.dll")
    paths = args.scripts or script_paths(args.dump)
    bootstrap = os.path.join(args.dump, BOOTSTRAP)
    if args.no_bootstrap or not os.path.exists(bootstrap):
        bootstrap = None
    else:
        paths = [p for p in paths
                 if os.path.normcase(p) != os.path.normcase(bootstrap)]
        paths.insert(0, bootstrap)
    failed = False
    with LuaHost(lua) as host:
        print("lua=%s" % host.lua_path)
        print("bootstrap=%s" % (bootstrap or "-"))
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
