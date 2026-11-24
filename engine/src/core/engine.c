#include "internal.h"

#include "lauxlib.h"
#include "lualib.h"

void r6_set_error(r6_engine *engine, const char *message) {
    size_t n = 0;
    if (!engine) {
        return;
    }
    if (message) {
        while (message[n] && n + 1 < R6_ERROR_CAP) {
            engine->error[n] = message[n];
            n++;
        }
    }
    engine->error[n] = 0;
}

void r6_log(r6_engine *engine, int level, const char *message) {
    if (engine && engine->log) {
        engine->log(engine->log_user, level, message, r6_strlen(message));
    }
}

size_t r6_engine_size(void) {
    return sizeof(r6_engine);
}

r6_engine *r6_engine_init(void *storage, size_t size, const r6_config *config) {
    r6_engine *engine;
    if (!storage || size < sizeof(r6_engine)) {
        return 0;
    }
    engine = (r6_engine *)storage;
    r6_memset(engine, 0, sizeof(*engine));
    if (config) {
        engine->log = config->log;
        engine->log_user = config->log_user;
        r6_arena_init(&engine->arena, config->arena, config->arena_size);
    }
    engine->L = luaL_newstate();
    if (!engine->L) {
        r6_set_error(engine, "luaL_newstate failed");
        return 0;
    }
    luaL_openlibs(engine->L);
    r6_log(engine, 0, "engine ready");
    return engine;
}

void r6_engine_shutdown(r6_engine *engine) {
    if (!engine) {
        return;
    }
    if (engine->L) {
        lua_close(engine->L);
        engine->L = 0;
    }
    r6_memset(engine, 0, sizeof(*engine));
}

int r6_engine_last_error(const r6_engine *engine, char *buf, size_t cap) {
    size_t i = 0;
    if (!buf || cap == 0) {
        return R6_ERR_ARG;
    }
    if (engine) {
        while (engine->error[i] && i + 1 < cap) {
            buf[i] = engine->error[i];
            i++;
        }
    }
    buf[i] = 0;
    return R6_OK;
}
