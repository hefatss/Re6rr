/* Bounded reader for the shipped Lua global inventory. No files, allocator or
 * Lua state: the host supplies the derived blob and caller buffers. */

#include "r6/r6_lua_globals.h"

#include "core/internal.h"

static const unsigned char lua_globals_magic[8] = {
    'R', '6', 'L', 'U', 'A', 0, 1, 0
};

int r6_lua_globals_parse(const void *data, size_t size,
                         r6_lua_globals_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t strings_off;
    if (!bytes || !out || size < 24u ||
        r6_memcmp(bytes, lua_globals_magic, sizeof(lua_globals_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->count = r6_u32(bytes, 12);
    if (out->count != R6_LUA_GLOBALS_COUNT) {
        return R6_ERR_FORMAT;
    }
    strings_off = 24u + out->count * 12u;
    out->strings_off = r6_u32(bytes, 16);
    out->strings_size = r6_u32(bytes, 20);
    if (out->strings_off != strings_off || !out->strings_size ||
        (uint64_t)strings_off + out->strings_size != size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_lua_globals_row(const void *data, size_t size, uint32_t index,
                       char *name, size_t capacity, uint32_t *calls,
                       uint32_t *category) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lua_globals_header header;
    uint32_t offset;
    uint32_t end;
    uint32_t at;
    uint32_t group;
    if (r6_lua_globals_parse(data, size, &header) != R6_OK ||
        index >= header.count || !name || !capacity) {
        return R6_ERR_ARG;
    }
    offset = 24u + index * 12u;
    group = r6_u32(bytes, offset + 8u);
    if (group >= R6_LUA_GLOBALS_CATEGORIES) {
        return R6_ERR_FORMAT;
    }
    offset = r6_u32(bytes, offset);
    if (offset < header.strings_off ||
        offset >= header.strings_off + header.strings_size) {
        return R6_ERR_FORMAT;
    }
    end = header.strings_off + header.strings_size;
    at = offset;
    while (at < end && bytes[at]) {
        at++;
    }
    if (at == end || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(name, bytes + offset, at - offset);
    name[at - offset] = 0;
    if (calls) {
        *calls = r6_u32(bytes, 24u + index * 12u + 4u);
    }
    if (category) {
        *category = group;
    }
    return R6_OK;
}

int r6_lua_globals_find(const void *data, size_t size, const char *name,
                        uint32_t *index) {
    r6_lua_globals_header header;
    size_t wanted;
    uint32_t at;
    int result = r6_lua_globals_parse(data, size, &header);
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
    for (at = 0; at < header.count; at++) {
        char found[R6_LUA_GLOBALS_NAME_CAP];
        result = r6_lua_globals_row(data, size, at, found, sizeof(found), NULL,
                                    NULL);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(found) == wanted &&
            r6_memcmp(found, name, wanted) == 0) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}
