"""Build the freestanding engine core as a Windows test DLL and run its tests.

    python tools/engine/build_host.py [--dump DIR] [--test]

The Android build will use the NDK and the same sources. This host build
exists so the C core can be executed against the real dump without a CRT:
clang emits a DLL with no imports beyond lua5.1.dll, and Python loads it with
ctypes.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CLANG = os.environ.get("CLANG", r"C:\Program Files\LLVM\bin\clang.exe")
DLLTOOL = os.environ.get("DLLTOOL", r"C:\Program Files\LLVM\bin\llvm-dlltool.exe")
READOBJ = os.environ.get("LLVM_READOBJ", r"C:\Program Files\LLVM\bin\llvm-readobj.exe")

SOURCES = [
    "engine/src/core/mem.c",
    "engine/src/core/engine.c",
    "engine/src/core/lua_host.c",
    "engine/src/core/context.c",
    "engine/src/assets/xmd.c",
    "engine/src/assets/ndwd.c",
    "engine/src/assets/ntwd.c",
    "engine/src/host/dllmain.c",
]


def lua_import_library(dump, out_dir):
    dll = os.path.join(dump, "lua5.1.dll")
    if not os.path.exists(dll):
        raise SystemExit("lua5.1.dll not found in %s" % dump)
    os.makedirs(out_dir, exist_ok=True)
    lib = os.path.join(out_dir, "lua5.1.lib")
    if os.path.exists(lib):
        return lib
    text = subprocess.run([READOBJ, "--coff-exports", dll],
                          capture_output=True, text=True, check=True).stdout
    names = re.findall(r"Name: (\S+)", text)
    def_path = os.path.join(out_dir, "lua5.1.def")
    with open(def_path, "w", encoding="ascii") as f:
        f.write("LIBRARY lua5.1.dll\nEXPORTS\n")
        for name in names:
            f.write("  %s\n" % name)
    subprocess.run([DLLTOOL, "-m", "i386:x86-64", "-d", def_path, "-l", lib],
                   check=True)
    return lib


def build(dump, out_dir):
    lib = lua_import_library(dump, out_dir)
    out = os.path.join(out_dir, "r6_engine.dll")
    cmd = [
        CLANG, "-std=c11", "-O2", "-g", "-shared", "-nostdlib",
        "-fno-stack-protector", "-fno-builtin", "-ffreestanding",
        "-DR6_BUILD_DLL", "-DLUA_BUILD_AS_DLL",
        "-I", os.path.join(ROOT, "engine", "include"),
        "-I", os.path.join(ROOT, "engine", "src"),
        "-I", os.path.join(ROOT, "engine", "compat"),
        "-I", os.path.join(ROOT, "third_party", "lua-5.1.5", "src"),
        "-Wl,/nodefaultlib", "-Wl,/entry:DllMain",
        "-o", out,
    ] + [os.path.join(ROOT, src) for src in SOURCES] + [lib]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("built %s" % out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                     r"D:\Games\W6W-05"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "engine"))
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    dll = build(args.dump, args.out)
    if args.test:
        test = os.path.join(ROOT, "tools", "engine", "test_engine.py")
        subprocess.run([sys.executable, test, "--dump", args.dump,
                        "--dll", dll], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
