/* Freestanding reader for shipped luaL_Reg tables. The derived blob comes
 * from tools/engine/lua_reg_tables_catalog.py. Labels that look like
 * signatures are copied verbatim and are not interpreted. */
#ifndef R6_LUA_REG_TABLES_H
#define R6_LUA_REG_TABLES_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_LUA_REG_TABLES = 3,
    R6_LUA_REG_ENTRIES = 42,
    R6_LUA_REG_USERS = 1,
    R6_LUA_REG_NAME_CAP = 256
};

typedef struct r6_lua_reg_header {
    uint32_t version;
    uint32_t table_count;
    uint32_t entry_count;
    uint32_t user_count;
    uint32_t strings_size;
} r6_lua_reg_header;

R6_API int r6_lua_reg_parse(const void *data, size_t size,
                            r6_lua_reg_header *out);

R6_API int r6_lua_reg_table(const void *data, size_t size, uint32_t index,
                            uint32_t *rva, uint32_t *table_size,
                            uint32_t *stride, uint32_t *count,
                            uint32_t *entry_first, uint32_t *user_first,
                            uint32_t *user_count);

R6_API int r6_lua_reg_entry(const void *data, size_t size, uint32_t index,
                            char *name, size_t capacity, uint32_t *func_rva);

R6_API int r6_lua_reg_table_entry(const void *data, size_t size,
                                  uint32_t table_index, uint32_t local_index,
                                  char *name, size_t capacity,
                                  uint32_t *func_rva);

R6_API int r6_lua_reg_user(const void *data, size_t size, uint32_t index,
                           uint32_t *rva);

/* First exact name match across the shipped tables. */
R6_API int r6_lua_reg_find(const void *data, size_t size, const char *name,
                           uint32_t *table_index, uint32_t *local_index,
                           uint32_t *global_index);

/* All global entry indexes with that exact function RVA, in stored order.
 * *count gets the total; up to capacity indexes are copied. R6_ERR_NOT_FOUND
 * means none, R6_ERR_BUFFER means the capacity was short. */
R6_API int r6_lua_reg_find_rva(const void *data, size_t size, uint32_t rva,
                               uint32_t *indices, uint32_t capacity,
                               uint32_t *count);

#ifdef __cplusplus
}
#endif

#endif
