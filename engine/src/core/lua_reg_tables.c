/* Bounded reader for the derived luaL_Reg inventory. RVAs are data only. */

#include "r6/r6_lua_reg_tables.h"

#include "core/internal.h"

static const unsigned char lua_reg_magic[8] = {
    'R', '6', 'L', 'R', 'E', 'G', 0, 1
};

enum {
    R6_LUA_REG_HEADER_SIZE = 28,
    R6_LUA_REG_TABLE_OFF = 28,
    R6_LUA_REG_ENTRY_OFF = R6_LUA_REG_TABLE_OFF + R6_LUA_REG_TABLES * 28u,
    R6_LUA_REG_USER_OFF = R6_LUA_REG_ENTRY_OFF + R6_LUA_REG_ENTRIES * 8u,
    R6_LUA_REG_STRING_OFF = R6_LUA_REG_USER_OFF + R6_LUA_REG_USERS * 4u
};

static int lua_reg_header(const void *data, size_t size,
                          r6_lua_reg_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lua_reg_header header;
    if (!bytes || !out || size < R6_LUA_REG_HEADER_SIZE ||
        r6_memcmp(bytes, lua_reg_magic, sizeof(lua_reg_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_LUA_REG_TABLES ||
        r6_u32(bytes, 16) != R6_LUA_REG_ENTRIES ||
        r6_u32(bytes, 20) != R6_LUA_REG_USERS) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.table_count = r6_u32(bytes, 12);
    header.entry_count = r6_u32(bytes, 16);
    header.user_count = r6_u32(bytes, 20);
    header.strings_size = r6_u32(bytes, 24);
    if (!header.strings_size ||
        (size_t)R6_LUA_REG_STRING_OFF + header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int lua_reg_name(const void *data, size_t size, uint32_t offset,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t at = offset;
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (offset < R6_LUA_REG_STRING_OFF || offset >= size) {
        return R6_ERR_FORMAT;
    }
    while (at < size && bytes[at]) {
        at++;
    }
    if (at == size || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, at - offset);
    out[at - offset] = 0;
    return R6_OK;
}

int r6_lua_reg_parse(const void *data, size_t size, r6_lua_reg_header *out) {
    return lua_reg_header(data, size, out);
}

int r6_lua_reg_table(const void *data, size_t size, uint32_t index,
                     uint32_t *rva, uint32_t *table_size, uint32_t *stride,
                     uint32_t *count, uint32_t *entry_first,
                     uint32_t *user_first, uint32_t *user_count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lua_reg_header header;
    uint32_t row_off;
    uint32_t number;
    uint32_t step;
    int result = lua_reg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.table_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_LUA_REG_TABLE_OFF + index * 28u;
    number = r6_u32(bytes, row_off + 12u);
    step = r6_u32(bytes, row_off + 8u);
    if (r6_u32(bytes, row_off + 4u) != number * step ||
        r6_u32(bytes, row_off + 16u) + number > header.entry_count ||
        r6_u32(bytes, row_off + 20u) + r6_u32(bytes, row_off + 24u) >
            header.user_count) {
        return R6_ERR_FORMAT;
    }
    if (rva) {
        *rva = r6_u32(bytes, row_off);
    }
    if (table_size) {
        *table_size = r6_u32(bytes, row_off + 4u);
    }
    if (stride) {
        *stride = step;
    }
    if (count) {
        *count = number;
    }
    if (entry_first) {
        *entry_first = r6_u32(bytes, row_off + 16u);
    }
    if (user_first) {
        *user_first = r6_u32(bytes, row_off + 20u);
    }
    if (user_count) {
        *user_count = r6_u32(bytes, row_off + 24u);
    }
    return R6_OK;
}

int r6_lua_reg_entry(const void *data, size_t size, uint32_t index,
                     char *name, size_t capacity, uint32_t *func_rva) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lua_reg_header header;
    uint32_t row_off;
    int result = lua_reg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.entry_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_LUA_REG_ENTRY_OFF + index * 8u;
    result = lua_reg_name(data, size, r6_u32(bytes, row_off), name, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (func_rva) {
        *func_rva = r6_u32(bytes, row_off + 4u);
    }
    return R6_OK;
}

int r6_lua_reg_table_entry(const void *data, size_t size,
                           uint32_t table_index, uint32_t local_index,
                           char *name, size_t capacity, uint32_t *func_rva) {
    uint32_t first = 0;
    uint32_t count = 0;
    int result = r6_lua_reg_table(data, size, table_index, NULL, NULL, NULL,
                                  &count, &first, NULL, NULL);
    if (result != R6_OK) {
        return result;
    }
    if (local_index >= count) {
        return R6_ERR_ARG;
    }
    return r6_lua_reg_entry(data, size, first + local_index, name, capacity,
                            func_rva);
}

int r6_lua_reg_user(const void *data, size_t size, uint32_t index,
                    uint32_t *rva) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lua_reg_header header;
    int result = lua_reg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.user_count) {
        return R6_ERR_ARG;
    }
    if (rva) {
        *rva = r6_u32(bytes, R6_LUA_REG_USER_OFF + index * 4u);
    }
    return R6_OK;
}

int r6_lua_reg_find_rva(const void *data, size_t size, uint32_t rva,
                        uint32_t *indices, uint32_t capacity,
                        uint32_t *count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lua_reg_header header;
    uint32_t total = 0;
    uint32_t copied = 0;
    uint32_t global;
    int result = lua_reg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (rva < 0x1000u || rva >= 34308096u || (capacity && !indices)) {
        return R6_ERR_ARG;
    }
    for (global = 0; global < header.entry_count; global++) {
        uint32_t found = r6_u32(bytes, R6_LUA_REG_ENTRY_OFF + global * 8u + 4u);
        if (found == rva) {
            if (copied < capacity) {
                indices[copied++] = global;
            }
            total++;
        }
    }
    if (count) {
        *count = total;
    }
    if (!total) {
        return R6_ERR_NOT_FOUND;
    }
    return total > capacity ? R6_ERR_BUFFER : R6_OK;
}

int r6_lua_reg_find(const void *data, size_t size, const char *name,
                    uint32_t *table_index, uint32_t *local_index,
                    uint32_t *global_index) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lua_reg_header header;
    size_t wanted;
    uint32_t global = 0;
    uint32_t local;
    uint32_t table;
    int result = lua_reg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!name) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (table = 0; table < header.table_count; table++) {
        uint32_t count = r6_u32(bytes, R6_LUA_REG_TABLE_OFF + table * 28u +
                                      12u);
        for (local = 0; local < count; local++) {
            uint32_t offset = r6_u32(bytes, R6_LUA_REG_ENTRY_OFF +
                                           global * 8u);
            uint32_t end = offset;
            while (end < size && bytes[end]) {
                end++;
            }
            if (end < size && end - offset == wanted &&
                r6_memcmp(bytes + offset, name, wanted) == 0) {
                if (table_index) {
                    *table_index = table;
                }
                if (local_index) {
                    *local_index = local;
                }
                if (global_index) {
                    *global_index = global;
                }
                return R6_OK;
            }
            global++;
        }
    }
    return R6_ERR_NOT_FOUND;
}
