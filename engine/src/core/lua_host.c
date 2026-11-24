#include "internal.h"

#include "lauxlib.h"
#include "lualib.h"

static void error_name(r6_engine *engine, const char *prefix, const char *name) {
    char buf[R6_ERROR_CAP];
    size_t at = 0;
    while (prefix[at] && at + 1 < R6_ERROR_CAP) {
        buf[at] = prefix[at];
        at++;
    }
    while (name && *name && at + 1 < R6_ERROR_CAP) {
        buf[at++] = *name++;
    }
    buf[at] = 0;
    r6_set_error(engine, buf);
}

static void error_lua(r6_engine *engine) {
    const char *message = lua_tostring(engine->L, -1);
    r6_set_error(engine, message ? message : "unspecified Lua error");
}

static void set_number_field(lua_State *L, const char *key, double value) {
    lua_pushnumber(L, (lua_Number)value);
    lua_setfield(L, -2, key);
}

static void set_setting_table(lua_State *L, const char *name,
                              const char *const *keys, const int *values,
                              size_t count) {
    size_t i;
    lua_createtable(L, 0, (int)count);
    for (i = 0; i < count; i++) {
        set_number_field(L, keys[i], (double)values[i]);
    }
    lua_setfield(L, -2, name);
}

int r6_engine_load_script(r6_engine *engine, const char *chunk_name,
                          const void *data, size_t size) {
    const char *bytes = (const char *)data;
    const char *name = chunk_name ? chunk_name : "?";
    int base;
    int rc;
    if (!engine || !engine->L || !data || size == 0) {
        return R6_ERR_ARG;
    }
    /* LuabindPack::luaL_loadbuffer skips a UTF-8 BOM before compiling. */
    if (size >= 3 && (unsigned char)bytes[0] == 0xEF &&
        (unsigned char)bytes[1] == 0xBB && (unsigned char)bytes[2] == 0xBF) {
        bytes += 3;
        size -= 3;
    }
    base = lua_gettop(engine->L);
    rc = luaL_loadbuffer(engine->L, bytes, size, name);
    if (rc == 0) {
        rc = lua_pcall(engine->L, 0, 0, 0);
    }
    if (rc != 0) {
        error_lua(engine);
        lua_settop(engine->L, base);
        return R6_ERR_SCRIPT;
    }
    lua_settop(engine->L, base);
    return R6_OK;
}

int r6_engine_set_number(r6_engine *engine, const char *name, double value) {
    if (!engine || !engine->L || !name) {
        return R6_ERR_ARG;
    }
    lua_pushnumber(engine->L, (lua_Number)value);
    lua_setfield(engine->L, LUA_GLOBALSINDEX, name);
    return R6_OK;
}

int r6_engine_set_setting_const(r6_engine *engine) {
    static const char *const locale_keys[] = {
        "Japan", "Usa", "China", "Korea", "Euro"
    };
    static const int locale_values[] = { 0, 1, 2, 3, 4 };
    static const char *const language_keys[] = { "Japanese", "English" };
    static const int language_values[] = { 0, 1 };
    static const char *const difficult_keys[] = {
        "VeryEasy", "Easy", "Normal", "Hard", "VeryHard"
    };
    static const int difficult_values[] = { 0, 1, 2, 3, 4 };
    static const char *const mode_keys[] = {
        "Network_Disable", "Network_Enable", "Disable", "Enable"
    };
    static const int mode_values[] = { 0, 1, 0, 1 };
    static const char *const ffb_keys[] = {
        "Disable", "TorqueLevel2", "TorqueLevel3"
    };
    static const int ffb_values[] = { 0, 1, 2 };
    static const char *const state_keys[] = { "Disable", "Enable" };
    static const int state_values[] = { 0, 1 };
    char id_name[16];
    int i;
    if (!engine || !engine->L) {
        return R6_ERR_ARG;
    }
    lua_createtable(engine->L, 0, 7);
    set_setting_table(engine->L, "Locale", locale_keys, locale_values, 5);
    set_setting_table(engine->L, "Language", language_keys, language_values, 2);
    set_setting_table(engine->L, "Difficult", difficult_keys, difficult_values, 5);
    set_setting_table(engine->L, "NetworkMode", mode_keys, mode_values, 4);
    set_setting_table(engine->L, "ForceFeedBackLevel", ffb_keys, ffb_values, 3);
    set_setting_table(engine->L, "State", state_keys, state_values, 2);
    lua_createtable(engine->L, 0, 8);
    for (i = 0; i < 8; i++) {
        id_name[0] = 'N'; id_name[1] = 'e'; id_name[2] = 't'; id_name[3] = 'w';
        id_name[4] = 'o'; id_name[5] = 'r'; id_name[6] = 'k'; id_name[7] = 'I';
        id_name[8] = 'D'; id_name[9] = '_'; id_name[10] = (char)('0' + i);
        id_name[11] = 0;
        set_number_field(engine->L, id_name, (double)i);
    }
    lua_setfield(engine->L, -2, "NetworkID");
    lua_setfield(engine->L, LUA_GLOBALSINDEX, "SettingConst");
    return R6_OK;
}

int r6_engine_has_function(r6_engine *engine, const char *name) {
    int base;
    int found;
    if (!engine || !engine->L || !name) {
        return 0;
    }
    base = lua_gettop(engine->L);
    lua_getfield(engine->L, LUA_GLOBALSINDEX, name);
    found = lua_isfunction(engine->L, -1);
    lua_settop(engine->L, base);
    return found;
}

static int call_begin(r6_engine *engine, const char *name, int *base) {
    if (!engine || !engine->L || !name) {
        return R6_ERR_ARG;
    }
    *base = lua_gettop(engine->L);
    lua_getfield(engine->L, LUA_GLOBALSINDEX, name);
    if (!lua_isfunction(engine->L, -1)) {
        lua_settop(engine->L, *base);
        error_name(engine, "missing Lua function: ", name);
        return R6_ERR_NOT_FOUND;
    }
    return R6_OK;
}

static int call_finish(r6_engine *engine, int base, int argc) {
    int rc = lua_pcall(engine->L, argc, LUA_MULTRET, 0);
    if (rc != 0) {
        error_lua(engine);
        lua_settop(engine->L, base);
        return R6_ERR_LUA;
    }
    return R6_OK;
}

static void zero_vec3(float out[3]) {
    if (out) {
        out[0] = 0.0f;
        out[1] = 0.0f;
        out[2] = 0.0f;
    }
}

static int read_vec3(r6_engine *engine, int base, float out[3]) {
    int count;
    if (!out) {
        lua_settop(engine->L, base);
        return R6_ERR_ARG;
    }
    count = lua_gettop(engine->L) - base;
    if (count < 3 || lua_type(engine->L, -3) != LUA_TNUMBER ||
        lua_type(engine->L, -2) != LUA_TNUMBER ||
        lua_type(engine->L, -1) != LUA_TNUMBER) {
        lua_settop(engine->L, base);
        r6_set_error(engine, "Lua function did not return three numbers");
        return R6_ERR_FORMAT;
    }
    out[0] = (float)lua_tonumber(engine->L, -3);
    out[1] = (float)lua_tonumber(engine->L, -2);
    out[2] = (float)lua_tonumber(engine->L, -1);
    lua_settop(engine->L, base);
    return R6_OK;
}

int r6_engine_call_vec3_key(r6_engine *engine, const char *name,
                            const char *key, int index, float out[3]) {
    int base;
    int rc;
    zero_vec3(out);
    rc = call_begin(engine, name, &base);
    if (rc != R6_OK) {
        return rc;
    }
    lua_pushstring(engine->L, key ? key : "");
    lua_pushinteger(engine->L, (lua_Integer)index);
    rc = call_finish(engine, base, 2);
    if (rc != R6_OK) {
        return rc;
    }
    return read_vec3(engine, base, out);
}

int r6_engine_call_vec3_index(r6_engine *engine, const char *name,
                              int index, float out[3]) {
    int base;
    int rc;
    zero_vec3(out);
    rc = call_begin(engine, name, &base);
    if (rc != R6_OK) {
        return rc;
    }
    lua_pushinteger(engine->L, (lua_Integer)index);
    rc = call_finish(engine, base, 1);
    if (rc != R6_OK) {
        return rc;
    }
    return read_vec3(engine, base, out);
}

int r6_engine_call_number(r6_engine *engine, const char *name, double *out) {
    int base;
    int count;
    int rc;
    if (out) {
        *out = 0.0;
    }
    rc = call_begin(engine, name, &base);
    if (rc != R6_OK) {
        return rc;
    }
    rc = call_finish(engine, base, 0);
    if (rc != R6_OK) {
        return rc;
    }
    count = lua_gettop(engine->L) - base;
    if (!out || count < 1 || lua_type(engine->L, -1) != LUA_TNUMBER) {
        lua_settop(engine->L, base);
        r6_set_error(engine, "Lua function did not return a number");
        return R6_ERR_FORMAT;
    }
    *out = (double)lua_tonumber(engine->L, -1);
    lua_settop(engine->L, base);
    return R6_OK;
}
