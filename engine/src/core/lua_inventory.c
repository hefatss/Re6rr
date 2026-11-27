/* Bounded reader for the derived Lua script inventory. No dump access, file
 * enumeration or Lua parsing happens inside the core. */

#include "r6/r6_lua_inventory.h"

#include "core/internal.h"

static const unsigned char lua_inventory_magic[8] = {
    'R', '6', 'L', 'S', 'I', 0, 1, 0
};

static int inventory_header(const void *data, size_t size,
                            r6_lua_inventory_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t rows_end = 124u + R6_LUA_INVENTORY_DIRS * 20u;
    uint32_t strings_off;
    uint32_t strings_size;
    uint32_t root;
    uint32_t kind;
    if (!bytes || !out || size < 124u ||
        r6_memcmp(bytes, lua_inventory_magic,
                  sizeof(lua_inventory_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_LUA_INVENTORY_ROOTS ||
        r6_u32(bytes, 64) != R6_LUA_INVENTORY_DIRS) {
        return R6_ERR_FORMAT;
    }
    strings_off = r6_u32(bytes, 68);
    strings_size = r6_u32(bytes, 72);
    if (!strings_size || strings_off < rows_end || strings_off > size ||
        (uint64_t)strings_off + strings_size != size) {
        return R6_ERR_FORMAT;
    }
    for (root = 0; root < R6_LUA_INVENTORY_ROOTS; root++) {
        for (kind = 0; kind < R6_LUA_INVENTORY_SYMBOL_KINDS; kind++) {
            uint32_t field = 76u + (root * R6_LUA_INVENTORY_SYMBOL_KINDS +
                                   kind) * 8u;
            uint32_t table_count = r6_u32(bytes, field);
            uint32_t table_off = r6_u32(bytes, field + 4u);
            uint32_t step = kind == R6_LUA_INVENTORY_DEFINED_NAMES ? 4u : 8u;
            if (!table_count || table_off < rows_end ||
                (uint64_t)table_off + (uint64_t)table_count * step >
                strings_off) {
                return R6_ERR_FORMAT;
            }
        }
    }
    r6_memset(out, 0, sizeof(*out));
    out->root_count = r6_u32(bytes, 12);
    out->dir_count = r6_u32(bytes, 64);
    out->strings_size = strings_size;
    out->files[0] = r6_u32(bytes, 16);
    out->bytes[0] = r6_u32(bytes, 20);
    out->defined[0] = r6_u32(bytes, 24);
    out->calls[0] = r6_u32(bytes, 28);
    out->undefined[0] = r6_u32(bytes, 32);
    out->native_candidates[0] = r6_u32(bytes, 36);
    out->files[1] = r6_u32(bytes, 40);
    out->bytes[1] = r6_u32(bytes, 44);
    out->defined[1] = r6_u32(bytes, 48);
    out->calls[1] = r6_u32(bytes, 52);
    out->undefined[1] = r6_u32(bytes, 56);
    out->native_candidates[1] = r6_u32(bytes, 60);
    out->defined_name_count[0] = r6_u32(bytes, 76);
    out->defined_name_off[0] = r6_u32(bytes, 80);
    out->native_top_count[0] = r6_u32(bytes, 84);
    out->native_top_off[0] = r6_u32(bytes, 88);
    out->undefined_top_count[0] = r6_u32(bytes, 92);
    out->undefined_top_off[0] = r6_u32(bytes, 96);
    out->defined_name_count[1] = r6_u32(bytes, 100);
    out->defined_name_off[1] = r6_u32(bytes, 104);
    out->native_top_count[1] = r6_u32(bytes, 108);
    out->native_top_off[1] = r6_u32(bytes, 112);
    out->undefined_top_count[1] = r6_u32(bytes, 116);
    out->undefined_top_off[1] = r6_u32(bytes, 120);
    return R6_OK;
}

static int inventory_name_at(const unsigned char *bytes, size_t size,
                             uint32_t offset, char *name, size_t capacity) {
    uint32_t rows_end = 124u + R6_LUA_INVENTORY_DIRS * 20u;
    uint32_t at = offset;
    if (offset < rows_end || offset >= size) {
        return R6_ERR_FORMAT;
    }
    while (at < size && bytes[at]) {
        at++;
    }
    if (at == size || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(name, bytes + offset, at - offset);
    name[at - offset] = 0;
    return R6_OK;
}

static int inventory_row_at(const void *data, size_t size, uint32_t index,
                            const unsigned char **bytes, uint32_t *row_off) {
    r6_lua_inventory_header header;
    int result = inventory_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.dir_count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = 124u + index * 20u;
    return R6_OK;
}

int r6_lua_inventory_parse(const void *data, size_t size,
                           r6_lua_inventory_header *out) {
    return inventory_header(data, size, out);
}

int r6_lua_inventory_name(const void *data, size_t size, uint32_t index,
                          char *name, size_t capacity) {
    const unsigned char *bytes;
    uint32_t row_off;
    int result = inventory_row_at(data, size, index, &bytes, &row_off);
    if (result != R6_OK || !name || !capacity) {
        return result == R6_OK ? R6_ERR_ARG : result;
    }
    return inventory_name_at(bytes, size, r6_u32(bytes, row_off + 4u),
                             name, capacity);
}

int r6_lua_inventory_dir(const void *data, size_t size, uint32_t index,
                         r6_lua_inventory_dir_t *out) {
    const unsigned char *bytes;
    uint32_t row_off;
    int result = inventory_row_at(data, size, index, &bytes, &row_off);
    if (result != R6_OK || !out) {
        return result == R6_OK ? R6_ERR_ARG : result;
    }
    if (r6_u32(bytes, row_off) >= R6_LUA_INVENTORY_ROOTS ||
        r6_u32(bytes, row_off + 4u) <
            124u + R6_LUA_INVENTORY_DIRS * 20u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->root = r6_u32(bytes, row_off);
    out->files = r6_u32(bytes, row_off + 8u);
    out->bytes = r6_u32(bytes, row_off + 12u);
    out->with_logic = r6_u32(bytes, row_off + 16u);
    return R6_OK;
}

int r6_lua_inventory_find(const void *data, size_t size, uint32_t root,
                          const char *name, uint32_t *index) {
    r6_lua_inventory_header header;
    const unsigned char *bytes;
    uint32_t length;
    uint32_t at;
    char candidate[R6_LUA_INVENTORY_NAME_CAP];
    int result = inventory_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (root >= header.root_count || !name || !index) {
        return R6_ERR_ARG;
    }
    length = (uint32_t)r6_strlen(name);
    if (!length || length >= sizeof(candidate)) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    for (at = 0; at < header.dir_count; at++) {
        uint32_t row_off = 124u + at * 20u;
        if (r6_u32(bytes, row_off) != root ||
            inventory_name_at(bytes, size, r6_u32(bytes, row_off + 4u),
                              candidate, sizeof(candidate)) != R6_OK) {
            if (r6_u32(bytes, row_off) != root) {
                continue;
            }
            return R6_ERR_FORMAT;
        }
        if (r6_memcmp(candidate, name, length) == 0 &&
            candidate[length] == 0) {
            *index = at;
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}


static int inventory_symbol_table(const void *data, size_t size, uint32_t root,
                                  uint32_t kind, const unsigned char **out_bytes,
                                  uint32_t *table_off, uint32_t *count,
                                  uint32_t *stride) {
    r6_lua_inventory_header header;
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t rows_end = 124u + R6_LUA_INVENTORY_DIRS * 20u;
    uint32_t strings_off;
    uint32_t table_count;
    uint32_t offset;
    uint32_t step = kind == R6_LUA_INVENTORY_DEFINED_NAMES ? 4u : 8u;
    uint64_t end;
    int result = inventory_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (root >= R6_LUA_INVENTORY_ROOTS || kind >= R6_LUA_INVENTORY_SYMBOL_KINDS) {
        return R6_ERR_ARG;
    }
    if (kind == R6_LUA_INVENTORY_DEFINED_NAMES) {
        table_count = header.defined_name_count[root];
        offset = header.defined_name_off[root];
    } else if (kind == R6_LUA_INVENTORY_NATIVE_TOP) {
        table_count = header.native_top_count[root];
        offset = header.native_top_off[root];
    } else {
        table_count = header.undefined_top_count[root];
        offset = header.undefined_top_off[root];
    }
    strings_off = r6_u32(bytes, 68);
    end = (uint64_t)offset + (uint64_t)table_count * step;
    if (offset < rows_end || end > strings_off || strings_off > size) {
        return R6_ERR_FORMAT;
    }
    *out_bytes = bytes;
    *table_off = offset;
    *count = table_count;
    *stride = step;
    return R6_OK;
}

static int inventory_symbol_at(const void *data, size_t size, uint32_t root,
                               uint32_t kind, uint32_t index, char *name,
                               size_t capacity, uint32_t *count) {
    const unsigned char *bytes;
    uint32_t table_off;
    uint32_t table_count;
    uint32_t stride;
    uint32_t row_off;
    int result = inventory_symbol_table(data, size, root, kind, &bytes,
                                        &table_off, &table_count, &stride);
    if (result != R6_OK) {
        return result;
    }
    if (index >= table_count || !name || !capacity) {
        return R6_ERR_ARG;
    }
    row_off = table_off + index * stride;
    if (count) {
        *count = kind == R6_LUA_INVENTORY_DEFINED_NAMES ?
                 0u : r6_u32(bytes, row_off + 4u);
    }
    return inventory_name_at(bytes, size, r6_u32(bytes, row_off), name,
                             capacity);
}

int r6_lua_inventory_symbol(const void *data, size_t size, uint32_t root,
                            uint32_t kind, uint32_t index, char *name,
                            size_t capacity, uint32_t *count) {
    return inventory_symbol_at(data, size, root, kind, index, name, capacity,
                               count);
}

int r6_lua_inventory_find_symbol(const void *data, size_t size, uint32_t root,
                                 uint32_t kind, const char *name,
                                 uint32_t *index, uint32_t *count) {
    const unsigned char *bytes;
    uint32_t table_off;
    uint32_t table_count;
    uint32_t stride;
    uint32_t at;
    size_t wanted;
    int result = inventory_symbol_table(data, size, root, kind, &bytes,
                                        &table_off, &table_count, &stride);
    if (result != R6_OK) {
        return result;
    }
    if (!name || !index) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < table_count; at++) {
        char candidate[R6_LUA_INVENTORY_NAME_CAP];
        uint32_t row_off = table_off + at * stride;
        result = inventory_name_at(bytes, size, r6_u32(bytes, row_off),
                                   candidate, sizeof(candidate));
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(candidate) == wanted &&
            r6_memcmp(candidate, name, wanted) == 0) {
            *index = at;
            if (count) {
                *count = kind == R6_LUA_INVENTORY_DEFINED_NAMES ?
                         0u : r6_u32(bytes, row_off + 4u);
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}
