/* Freestanding reader for the shipped Lua global call-site inventory. The
 * derived blob comes from tools/engine/lua_globals_catalog.py. */
#ifndef R6_LUA_GLOBALS_H
#define R6_LUA_GLOBALS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_LUA_GLOBALS_COUNT = 219,
    R6_LUA_GLOBALS_CATEGORIES = 7,
    R6_LUA_GLOBALS_NAME_CAP = 0x80
};

typedef struct r6_lua_globals_header {
    uint32_t count;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_lua_globals_header;

R6_API int r6_lua_globals_parse(const void *data, size_t size,
                                r6_lua_globals_header *out);

R6_API int r6_lua_globals_row(const void *data, size_t size, uint32_t index,
                              char *name, size_t capacity, uint32_t *calls,
                              uint32_t *category);

/* First exact global-name match; R6_ERR_NOT_FOUND means no row matched. */
R6_API int r6_lua_globals_find(const void *data, size_t size, const char *name,
                               uint32_t *index);

#ifdef __cplusplus
}
#endif

#endif
