/* Freestanding reader for shipped Lua script inventory counts and names. The
 * derived blob comes from tools/engine/lua_inventory_catalog.py. */
#ifndef R6_LUA_INVENTORY_H
#define R6_LUA_INVENTORY_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_LUA_INVENTORY_ROOTS = 2,
    R6_LUA_INVENTORY_DIRS = 158,
    R6_LUA_INVENTORY_NAME_CAP = 0x80,
    R6_LUA_INVENTORY_DEFINED_NAMES = 0,
    R6_LUA_INVENTORY_NATIVE_TOP = 1,
    R6_LUA_INVENTORY_UNDEFINED_TOP = 2,
    R6_LUA_INVENTORY_SYMBOL_KINDS = 3
};

typedef struct r6_lua_inventory_header {
    uint32_t root_count;
    uint32_t dir_count;
    uint32_t strings_size;
    uint32_t files[2];
    uint32_t bytes[2];
    uint32_t defined[2];
    uint32_t calls[2];
    uint32_t undefined[2];
    uint32_t native_candidates[2];
    uint32_t defined_name_count[2];
    uint32_t defined_name_off[2];
    uint32_t native_top_count[2];
    uint32_t native_top_off[2];
    uint32_t undefined_top_count[2];
    uint32_t undefined_top_off[2];
} r6_lua_inventory_header;

typedef struct r6_lua_inventory_dir_t {
    uint32_t root;
    uint32_t files;
    uint32_t bytes;
    uint32_t with_logic;
} r6_lua_inventory_dir_t;

R6_API int r6_lua_inventory_parse(const void *data, size_t size,
                                  r6_lua_inventory_header *out);

R6_API int r6_lua_inventory_name(const void *data, size_t size,
                                 uint32_t index, char *name, size_t capacity);

R6_API int r6_lua_inventory_dir(const void *data, size_t size,
                                uint32_t index, r6_lua_inventory_dir_t *out);

R6_API int r6_lua_inventory_find(const void *data, size_t size, uint32_t root,
                                 const char *name, uint32_t *index);

/* Shipped name lists per root: defined names and native/undefined top
 * name/count pairs. count is zero for defined names. */
R6_API int r6_lua_inventory_symbol(const void *data, size_t size,
                                   uint32_t root, uint32_t kind,
                                   uint32_t index, char *name,
                                   size_t capacity, uint32_t *count);

/* First exact name in one root/kind table. */
R6_API int r6_lua_inventory_find_symbol(const void *data, size_t size,
                                        uint32_t root, uint32_t kind,
                                        const char *name, uint32_t *index,
                                        uint32_t *count);

#ifdef __cplusplus
}
#endif

#endif
