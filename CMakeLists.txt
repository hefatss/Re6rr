cmake_minimum_required(VERSION 3.22)
project(re6rr VERSION 0.1 LANGUAGES C)

# Core, platform-independent engine. The host build in tools/engine/build_host.py
# compiles the same files with clang and links against the game's lua5.1.dll;
# this CMake build compiles Lua from third_party for Android instead.
set(R6_CORE
    engine/src/core/mem.c
    engine/src/core/engine.c
    engine/src/core/lua_host.c
    engine/src/core/context.c
    engine/src/core/lua_globals.c
    engine/src/core/lua_xrefs.c
    engine/src/core/lua_inventory.c
    engine/src/game/honor_schema.c
    engine/src/game/enma_enums.c
    engine/src/game/enma_defaults.c
    engine/src/game/enma_exports.c
    engine/src/game/scene_env.c
    engine/src/assets/xmd.c
    engine/src/assets/asset_inventory.c
    engine/src/assets/ndwd.c
    engine/src/assets/ntwd.c
    engine/src/assets/nut_texture.c
    engine/src/render/glsl_ubo.c
    engine/src/render/glsl_manifest.c
    engine/src/render/nsh.c
    engine/src/render/gles_host.c
    engine/src/render/vertex_layout.c
    engine/src/assets/inflate.c
    engine/src/audio/nub.c
    engine/src/audio/engmap.c
    engine/src/audio/emtis.c
    engine/src/audio/engine_sound.c
    engine/src/audio/bgm.c
    engine/src/audio/mixer.c
    engine/src/audio/envelope.c
    engine/src/audio/engine_runtime.c
    engine/src/audio/voice.c
    engine/src/audio/config_3d.c
    engine/src/physics/vehicle.c
    engine/src/physics/lua_config.c
    engine/src/physics/course.c
    engine/src/physics/race.c
    engine/src/game/game.c
    engine/src/game/stage_effect.c
    engine/src/game/car.c
    engine/src/game/custom.c
    engine/src/game/story.c
)

set(MINIZ_SRC third_party/miniz-2.2.0)
set(MINIZ_SOURCES
    ${MINIZ_SRC}/miniz.c
    ${MINIZ_SRC}/miniz_tinfl.c
    ${MINIZ_SRC}/miniz_tdef.c
)

set(LUA_SRC third_party/lua-5.1.5/src)
set(LUA_SOURCES
    ${LUA_SRC}/lapi.c ${LUA_SRC}/lcode.c ${LUA_SRC}/ldebug.c
    ${LUA_SRC}/ldo.c ${LUA_SRC}/ldump.c ${LUA_SRC}/lfunc.c
    ${LUA_SRC}/lgc.c ${LUA_SRC}/llex.c ${LUA_SRC}/lmem.c
    ${LUA_SRC}/lobject.c ${LUA_SRC}/lopcodes.c ${LUA_SRC}/lparser.c
    ${LUA_SRC}/lstate.c ${LUA_SRC}/lstring.c ${LUA_SRC}/ltable.c
    ${LUA_SRC}/ltm.c ${LUA_SRC}/lundump.c ${LUA_SRC}/lvm.c
    ${LUA_SRC}/lzio.c ${LUA_SRC}/lauxlib.c ${LUA_SRC}/lbaselib.c
    ${LUA_SRC}/ldblib.c ${LUA_SRC}/liolib.c ${LUA_SRC}/lmathlib.c
    ${LUA_SRC}/loslib.c ${LUA_SRC}/ltablib.c ${LUA_SRC}/lstrlib.c
    ${LUA_SRC}/loadlib.c ${LUA_SRC}/linit.c
)

add_library(lua51 STATIC ${LUA_SOURCES})
set_target_properties(lua51 PROPERTIES C_STANDARD 11)
target_compile_definitions(lua51 PRIVATE LUA_USE_LINUX LUA_USE_DLOPEN)
target_link_libraries(lua51 PUBLIC dl m)

add_library(r6core STATIC ${R6_CORE})
set_target_properties(r6core PROPERTIES C_STANDARD 11)
target_include_directories(r6core
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/engine/include
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/engine/src
            ${CMAKE_CURRENT_SOURCE_DIR}/engine/compat
            ${LUA_SRC} ${MINIZ_SRC} ${MINIZ_SRC}/compat)
target_compile_definitions(r6core PRIVATE
    MINIZ_NO_STDIO=1 MINIZ_NO_TIME=1 MINIZ_NO_DEFLATE_APIS=1
    MINIZ_NO_ARCHIVE_APIS=1 MINIZ_NO_MALLOC=1)
target_link_libraries(r6core PUBLIC lua51)

add_library(miniz STATIC ${MINIZ_SOURCES})
set_target_properties(miniz PROPERTIES C_STANDARD 11)
target_include_directories(miniz
    PRIVATE ${MINIZ_SRC} ${MINIZ_SRC}/compat ${CMAKE_CURRENT_SOURCE_DIR}/engine/compat)
target_compile_options(miniz PRIVATE
    -include ${CMAKE_CURRENT_SOURCE_DIR}/engine/compat/miniz_config.h)
target_link_libraries(r6core PUBLIC miniz)

if(ANDROID)
    # JNI platform layer: Java owns asset lookup and gzip reads, the core only
    # sees plain bytes. The core has no Android dependencies.
    add_library(r6engine SHARED engine/src/host/jni.c)
    target_link_libraries(r6engine PRIVATE r6core)
    find_library(ANDROID_LOG log)
    target_link_libraries(r6engine PRIVATE ${ANDROID_LOG})
endif()
