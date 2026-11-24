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
    engine/src/assets/xmd.c
    engine/src/assets/ndwd.c
    engine/src/assets/ntwd.c
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
            ${LUA_SRC})
target_link_libraries(r6core PUBLIC lua51)

if(ANDROID)
    # JNI platform layer is added here once the Android UI exists. The core
    # itself has no Android dependencies: callers pass already-inflated bytes.
    add_library(r6engine SHARED ${R6_CORE})
    target_link_libraries(r6engine PRIVATE lua51)
    find_library(ANDROID_LOG log)
    target_link_libraries(r6engine PRIVATE ${ANDROID_LOG})
endif()
