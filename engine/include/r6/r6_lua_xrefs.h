/* Freestanding reader for shipped Lua name -> native reference facts. The
 * derived blob comes from tools/engine/lua_xref_catalog.py. RVAs are reported
 * verbatim; no code is executed or decoded here. */
#ifndef R6_LUA_XREFS_H
#define R6_LUA_XREFS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_LUA_XREF_COUNT = 219,
    R6_LUA_XREF_NAME_CAP = 0x80,
    R6_LUA_XREF_VIA_CODE = 0,
    R6_LUA_XREF_VIA_TABLE = 1,
    R6_LUA_XREF_VIA_POINTER = 2,
    R6_LUA_XREF_KIND_STRINGS = 0,
    R6_LUA_XREF_KIND_POINTER = 1
};

typedef struct r6_lua_xref_header {
    uint32_t count;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_lua_xref_header;

typedef struct r6_lua_xref_row_t {
    uint32_t via;
    uint32_t func_count;
    uint32_t table_count;
} r6_lua_xref_row_t;

R6_API int r6_lua_xref_parse(const void *data, size_t size,
                             r6_lua_xref_header *out);

R6_API int r6_lua_xref_row(const void *data, size_t size, uint32_t index,
                           r6_lua_xref_row_t *out);

R6_API int r6_lua_xref_name(const void *data, size_t size, uint32_t index,
                            char *name, size_t capacity);

R6_API int r6_lua_xref_func(const void *data, size_t size, uint32_t index,
                            uint32_t which, uint32_t *rva);

R6_API int r6_lua_xref_table(const void *data, size_t size, uint32_t index,
                             uint32_t which, uint32_t *rva, uint32_t *kind,
                             uint32_t *user_count);

R6_API int r6_lua_xref_user(const void *data, size_t size, uint32_t index,
                            uint32_t which, uint32_t user, uint32_t *rva);

/* First exact name match; R6_ERR_NOT_FOUND means no row matched. */
R6_API int r6_lua_xref_find(const void *data, size_t size, const char *name,
                            uint32_t *index);

#ifdef __cplusplus
}
#endif

#endif
