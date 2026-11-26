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
    uint32_t rows_end = 76u + R6_LUA_INVENTORY_DIRS * 20u;
    uint32_t strings_size;
    if (!bytes || !out || size < 76u ||
        r6_memcmp(bytes, lua_inventory_magic,
                  sizeof(lua_inventory_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_LUA_INVENTORY_ROOTS ||
        r6_u32(bytes, 64) != R6_LUA_INVENTORY_DIRS ||
        r6_u32(bytes, 68) != rows_end) {
        return R6_ERR_FORMAT;
    }
    strings_size = r6_u32(bytes, 72);
    if (!strings_size || (uint64_t)rows_end + strings_size != size) {
        return R6_ERR_FORMAT;
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
    return R6_OK;
}

static int inventory_name_at(const unsigned char *bytes, size_t size,
                             uint32_t offset, char *name, size_t capacity) {
    uint32_t rows_end = 76u + R6_LUA_INVENTORY_DIRS * 20u;
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
    *row_off = 76u + index * 20u;
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
        r6_u32(bytes, row_off + 4u) < 76u + R6_LUA_INVENTORY_DIRS * 20u) {
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
        uint32_t row_off = 76u + at * 20u;
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
