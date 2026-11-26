/* Bounded reader for the recovered honor-condition schema. The executable
 * allocates 72 bytes per condition and exposes field order through label
 * providers; this reader only copies the recovered names. */

#include "r6/r6_honor_schema.h"

#include "core/internal.h"

static const unsigned char honor_schema_magic[8] = {
    'R', '6', 'H', 'O', 'N', 0, 1, 0
};

static int honor_header(const void *data, size_t size,
                        r6_honor_schema_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t strings_off;
    if (!bytes || !out || size < 24u ||
        r6_memcmp(bytes, honor_schema_magic, sizeof(honor_schema_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->type_count = r6_u32(bytes, 12);
    if (out->type_count != R6_HONOR_TYPES) {
        return R6_ERR_FORMAT;
    }
    strings_off = 24u + out->type_count * 28u;
    out->strings_off = r6_u32(bytes, 16);
    out->strings_size = r6_u32(bytes, 20);
    if (out->strings_off != strings_off || !out->strings_size ||
        (uint64_t)strings_off + out->strings_size != size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int honor_copy(const unsigned char *bytes,
                      const r6_honor_schema_header *header, uint32_t offset,
                      char *out, size_t capacity) {
    uint32_t end = header->strings_off + header->strings_size;
    uint32_t at;
    if (!offset || offset < header->strings_off || offset >= end) {
        return R6_ERR_FORMAT;
    }
    at = offset;
    while (at < end && bytes[at]) {
        at++;
    }
    if (at == end || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, at - offset);
    out[at - offset] = 0;
    return R6_OK;
}

int r6_honor_schema_parse(const void *data, size_t size,
                          r6_honor_schema_header *out) {
    return honor_header(data, size, out);
}

int r6_honor_schema_type(const void *data, size_t size, uint32_t type,
                         char *name, size_t capacity, uint32_t *field_count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_honor_schema_header header;
    uint32_t row;
    uint32_t count;
    int result;
    if (honor_header(data, size, &header) != R6_OK ||
        type >= header.type_count || !name || !capacity) {
        return R6_ERR_ARG;
    }
    row = 24u + type * 28u;
    count = r6_u32(bytes, row + 4u);
    if (count > R6_HONOR_FIELD_MAX) {
        return R6_ERR_FORMAT;
    }
    result = honor_copy(bytes, &header, r6_u32(bytes, row), name, capacity);
    if (result == R6_OK && field_count) {
        *field_count = count;
    }
    return result;
}

int r6_honor_schema_find_type(const void *data, size_t size,
                              const char *name, uint32_t *index) {
    r6_honor_schema_header header;
    size_t wanted;
    uint32_t at;
    int result = honor_header(data, size, &header);
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
    for (at = 0; at < header.type_count; at++) {
        char found[R6_HONOR_NAME_CAP];
        result = r6_honor_schema_type(data, size, at, found, sizeof(found),
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

int r6_honor_schema_field(const void *data, size_t size, uint32_t type,
                          uint32_t field, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_honor_schema_header header;
    uint32_t row;
    uint32_t count;
    if (honor_header(data, size, &header) != R6_OK ||
        type >= header.type_count || !out || !capacity) {
        return R6_ERR_ARG;
    }
    row = 24u + type * 28u;
    count = r6_u32(bytes, row + 4u);
    if (count > R6_HONOR_FIELD_MAX || field >= count) {
        return R6_ERR_ARG;
    }
    return honor_copy(bytes, &header,
                      r6_u32(bytes, row + 8u + field * 4u), out, capacity);
}
