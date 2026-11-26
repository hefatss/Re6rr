/* Bounded reader for the shipped Lua reference inventory. Every offset is
 * checked against the derived blob; no exe bytes are read by the core. */

#include "r6/r6_lua_xrefs.h"

#include "core/internal.h"

static const unsigned char lua_xref_magic[8] = {
    'R', '6', 'X', 'R', 'F', 0, 1, 0
};

static int xref_header(const void *data, size_t size,
                       r6_lua_xref_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint64_t arrays_end;
    if (!bytes || !out || size < 24u ||
        r6_memcmp(bytes, lua_xref_magic, sizeof(lua_xref_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->count = r6_u32(bytes, 12);
    if (out->count != R6_LUA_XREF_COUNT) {
        return R6_ERR_FORMAT;
    }
    arrays_end = 24u + (uint64_t)out->count * 24u;
    out->strings_off = r6_u32(bytes, 16);
    out->strings_size = r6_u32(bytes, 20);
    if (out->strings_off < arrays_end || !out->strings_size ||
        (uint64_t)out->strings_off + out->strings_size != size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int xref_row_at(const void *data, size_t size, uint32_t index,
                       const unsigned char **bytes, uint32_t *row_off,
                       r6_lua_xref_header *header) {
    if (xref_header(data, size, header) != R6_OK ||
        index >= header->count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = 24u + index * 24u;
    return R6_OK;
}

static int xref_array(uint32_t offset, uint32_t count, uint32_t arrays_end,
                      uint32_t strings_off) {
    if (!count) {
        return 1;
    }
    return offset >= arrays_end &&
           (uint64_t)offset + (uint64_t)count * 4u <= strings_off;
}

int r6_lua_xref_parse(const void *data, size_t size,
                      r6_lua_xref_header *out) {
    return xref_header(data, size, out);
}

int r6_lua_xref_row(const void *data, size_t size, uint32_t index,
                    r6_lua_xref_row_t *out) {
    r6_lua_xref_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t arrays_end;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = xref_row_at(data, size, index, &bytes, &row_off, &header);
    if (result != R6_OK) {
        return result;
    }
    arrays_end = 24u + header.count * 24u;
    r6_memset(out, 0, sizeof(*out));
    out->via = r6_u32(bytes, row_off + 4u);
    out->func_count = r6_u32(bytes, row_off + 8u);
    out->table_count = r6_u32(bytes, row_off + 16u);
    if (out->via > R6_LUA_XREF_VIA_POINTER ||
        out->func_count > header.strings_off / 4u ||
        out->table_count > header.strings_off / 24u ||
        !xref_array(r6_u32(bytes, row_off + 12u), out->func_count,
                    arrays_end, header.strings_off) ||
        !xref_array(r6_u32(bytes, row_off + 20u), out->table_count,
                    arrays_end, header.strings_off)) {
        r6_memset(out, 0, sizeof(*out));
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_lua_xref_name(const void *data, size_t size, uint32_t index,
                     char *name, size_t capacity) {
    r6_lua_xref_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t at;
    uint32_t end;
    uint32_t offset;
    int result;
    result = xref_row_at(data, size, index, &bytes, &row_off, &header);
    if (result != R6_OK || !name || !capacity) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, row_off);
    end = header.strings_off + header.strings_size;
    if (offset < header.strings_off || offset >= end) {
        return R6_ERR_FORMAT;
    }
    at = offset;
    while (at < end && bytes[at]) {
        at++;
    }
    if (at == end || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(name, bytes + offset, at - offset);
    name[at - offset] = 0;
    return R6_OK;
}

int r6_lua_xref_func(const void *data, size_t size, uint32_t index,
                     uint32_t which, uint32_t *rva) {
    r6_lua_xref_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t offset;
    uint32_t count;
    int result;
    result = xref_row_at(data, size, index, &bytes, &row_off, &header);
    if (result != R6_OK || !rva) {
        return R6_ERR_ARG;
    }
    count = r6_u32(bytes, row_off + 8u);
    if (which >= count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, row_off + 12u) + which * 4u;
    if (!xref_array(offset, 1u, 24u + header.count * 24u,
                    header.strings_off)) {
        return R6_ERR_FORMAT;
    }
    *rva = r6_u32(bytes, offset);
    return R6_OK;
}

int r6_lua_xref_table(const void *data, size_t size, uint32_t index,
                      uint32_t which, uint32_t *rva, uint32_t *kind,
                      uint32_t *user_count) {
    r6_lua_xref_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t offset;
    uint32_t count;
    uint32_t users;
    int result;
    result = xref_row_at(data, size, index, &bytes, &row_off, &header);
    if (result != R6_OK) {
        return result;
    }
    count = r6_u32(bytes, row_off + 16u);
    if (which >= count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, row_off + 20u) + which * 16u;
    if (!xref_array(offset, 4u, 24u + header.count * 24u,
                    header.strings_off)) {
        return R6_ERR_FORMAT;
    }
    users = r6_u32(bytes, offset + 12u);
    if (r6_u32(bytes, offset + 4u) > R6_LUA_XREF_KIND_POINTER ||
        !xref_array(users, r6_u32(bytes, offset + 8u),
                    24u + header.count * 24u, header.strings_off)) {
        return R6_ERR_FORMAT;
    }
    if (rva) {
        *rva = r6_u32(bytes, offset);
    }
    if (kind) {
        *kind = r6_u32(bytes, offset + 4u);
    }
    if (user_count) {
        *user_count = r6_u32(bytes, offset + 8u);
    }
    return R6_OK;
}

int r6_lua_xref_user(const void *data, size_t size, uint32_t index,
                     uint32_t which, uint32_t user, uint32_t *rva) {
    r6_lua_xref_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t offset;
    uint32_t count;
    uint32_t users;
    int result;
    result = xref_row_at(data, size, index, &bytes, &row_off, &header);
    if (result != R6_OK || !rva) {
        return R6_ERR_ARG;
    }
    count = r6_u32(bytes, row_off + 16u);
    if (which >= count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, row_off + 20u) + which * 16u;
    if (!xref_array(offset, 4u, 24u + header.count * 24u,
                    header.strings_off)) {
        return R6_ERR_FORMAT;
    }
    users = r6_u32(bytes, offset + 12u);
    count = r6_u32(bytes, offset + 8u);
    if (user >= count ||
        !xref_array(users + user * 4u, 1u, 24u + header.count * 24u,
                    header.strings_off)) {
        return R6_ERR_ARG;
    }
    *rva = r6_u32(bytes, users + user * 4u);
    return R6_OK;
}
