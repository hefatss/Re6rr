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
    "engine/src/core/lua_globals.c",
    "engine/src/core/lua_xrefs.c",
    "engine/src/core/lua_inventory.c",
    "engine/src/game/honor_schema.c",
    "engine/src/game/enma_enums.c",
    "engine/src/game/enma_defaults.c",
    "engine/src/game/enma_exports.c",
    "engine/src/game/scene_env.c",
    "engine/src/assets/xmd.c",
    "engine/src/assets/asset_inventory.c",
    "engine/src/core/pe_inventory.c",
    "engine/src/core/name_runs.c",
    "engine/src/core/lua_reg_tables.c",
    "engine/src/core/path_strings.c",
    "engine/src/core/enma_sim.c",
    "engine/src/core/ref_words.c",
    "engine/src/core/pdata_stats.c",
    "engine/src/core/string_xrefs.c",
    "engine/src/assets/ndwd.c",
    "engine/src/assets/ntwd.c",
    "engine/src/assets/nut_texture.c",
    "engine/src/render/glsl_ubo.c",
    "engine/src/render/glsl_manifest.c",
    "engine/src/render/nsh.c",
    "engine/src/render/gles_host.c",
    "engine/src/render/vertex_layout.c",
    "engine/src/render/shader_control_flow.c",
    "engine/src/assets/inflate.c",
    "engine/src/audio/nub.c",
    "engine/src/audio/engmap.c",
    "engine/src/audio/emtis.c",
    "engine/src/audio/engine_sound.c",
    "engine/src/audio/bgm.c",
    "engine/src/audio/mixer.c",
    "engine/src/audio/envelope.c",
    "engine/src/audio/engine_runtime.c",
    "engine/src/audio/voice.c",
    "engine/src/audio/config_3d.c",
    "engine/src/physics/vehicle.c",
    "engine/src/physics/lua_config.c",
    "engine/src/physics/course.c",
    "engine/src/physics/race.c",
    "engine/src/game/game.c",
    "engine/src/game/stage_effect.c",
    "engine/src/game/car.c",
    "engine/src/game/custom.c",
    "engine/src/game/story.c",
    "engine/src/host/dllmain.c",
]
MINIZ = [
    "third_party/miniz-2.2.0/miniz.c",
    "third_party/miniz-2.2.0/miniz_tinfl.c",
    "third_party/miniz-2.2.0/miniz_tdef.c",
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
    miniz_objs = []
    for index, source in enumerate(MINIZ):
        miniz_obj = os.path.join(out_dir, "miniz%d.obj" % index)
        miniz_cmd = [
            CLANG, "-std=c11", "-O2", "-c", "-fno-builtin", "-ffreestanding",
            "-mstack-probe-size=16777216",
            "-include", os.path.join(ROOT, "engine", "compat", "miniz_config.h"),
            "-I", os.path.join(ROOT, "third_party", "miniz-2.2.0", "compat"),
            "-I", os.path.join(ROOT, "third_party", "miniz-2.2.0"),
            "-I", os.path.join(ROOT, "engine", "compat"),
            os.path.join(ROOT, source), "-o", miniz_obj,
        ]
        subprocess.run(miniz_cmd, check=True)
        miniz_objs.append(miniz_obj)
    cmd = [
        CLANG, "-std=c11", "-O2", "-g", "-shared", "-nostdlib",
        "-fno-stack-protector", "-fno-builtin", "-ffreestanding",
        "-DR6_BUILD_DLL", "-DLUA_BUILD_AS_DLL",
        "-I", os.path.join(ROOT, "engine", "include"),
        "-I", os.path.join(ROOT, "engine", "src"),
        "-I", os.path.join(ROOT, "engine", "compat"),
        "-I", os.path.join(ROOT, "third_party", "lua-5.1.5", "src"),
        "-I", os.path.join(ROOT, "third_party", "miniz-2.2.0"),
        "-I", os.path.join(ROOT, "third_party", "miniz-2.2.0", "compat"),
        "-DMINIZ_NO_STDIO=1", "-DMINIZ_NO_TIME=1",
        "-DMINIZ_NO_DEFLATE_APIS=1", "-DMINIZ_NO_ARCHIVE_APIS=1",
        "-DMINIZ_NO_MALLOC=1",
        "-Wl,/nodefaultlib", "-Wl,/entry:DllMain",
        "-o", out,
    ] + [os.path.join(ROOT, src) for src in SOURCES] + miniz_objs + [lib]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("built %s" % out)
    return out


def check_jni(dump):
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        return
    command = [
        CLANG, "-std=c11", "-fsyntax-only",
        "-I", os.path.join(ROOT, "engine", "compat"),
        "-I", os.path.join(ROOT, "engine", "include"),
        "-I", os.path.join(java_home, "include"),
        "-I", os.path.join(java_home, "include", "win32"),
        os.path.join(ROOT, "engine", "src", "host", "jni.c"),
    ]
    subprocess.run(command, check=True)
    print("JNI layer syntax OK")
    javac = os.path.join(java_home, "bin", "javac.exe" if os.name == "nt"
                         else "javac")
    java_dir = os.path.join(ROOT, "platform", "android", "java", "com",
                            "wmmt", "re6rr")
    if os.path.exists(javac) and os.path.isdir(java_dir):
        classes = os.path.join(ROOT, "build", "tmp", "jni-classes")
        os.makedirs(classes, exist_ok=True)
        sources = [os.path.join(java_dir, name)
                   for name in ("Re6Engine.java", "AssetProvider.java",
                                "GlslBindings.java", "Re6Texture.java",
                                "Re6Audio.java", "EngineSound.java",
                                "VertexLayout.java", "BgmCatalog.java",
                                "EngineRuntime.java", "VoiceRequest.java",
                                "Config3D.java", "BankSetup.java",
                                "AudioStream.java", "VoiceChain.java",
                                "SoundInit.java", "BgmFade.java",
                                "SoundDispatch.java", "SceneBridge.java",
                                "StageEffect.java", "BgmManager.java",
                                "SoundConfig.java", "BankSlots.java",
                                "CourseSurface.java", "SoundStrings.java", "LuaAudioBindings.java", "EesCamera.java", "SceneConfig.java", "EesCarEffect.java", "EesCarDisp.java", "EesContainer.java", "EesCarInfo.java", "VoiceDispatchFacts.java", "VoiceCoreTableFacts.java", "AudioLayoutFacts.java", "NshContainer.java", "EnvironmentLua.java", "EngmapTable.java", "EmtisTable.java", "NativeNames.java", "ContextPaths.java", "LuaGlobals.java", "LuaXrefs.java", "HonorSchema.java", "EnmaEnums.java", "EnmaDefaults.java", "EnmaExports.java", "SceneEnvStats.java", "LuaInventory.java", "AssetInventory.java", "PeInventory.java", "NameRuns.java", "LuaRegTables.java", "PathStrings.java", "EnmaSimFacts.java", "RefWords.java", "PdataStats.java", "StringXrefs.java", "ShaderControlFlow.java")]
        subprocess.run([javac, "-d", classes] + sources, check=True)
        print("Java bridge compiles OK")
        subprocess.run([os.path.join(java_home, "bin", "java.exe" if os.name == "nt"
                                     else "java"), "-cp", classes,
                        "com.wmmt.re6rr.AssetProvider", dump], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                     r"D:\Games\W6W-05"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "engine"))
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    dll = build(args.dump, args.out)
    check_jni(args.dump)
    if args.test:
        test = os.path.join(ROOT, "tools", "engine", "test_engine.py")
        subprocess.run([sys.executable, test, "--dump", args.dump,
                        "--dll", dll], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
