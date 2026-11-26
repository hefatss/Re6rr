/* Bounded reader for the exported Enma symbol names. No DLL loading, symbol
 * resolution or allocation: the host supplies the derived blob and buffers. */

#include "r6/r6_enma_exports.h"

#include "core/internal.h"

static const unsigned char enma_exports_magic[8] = {
    'R', '6', 'E', 'E', 'X', 0, 1, 0
};

static int exports_header(const void *data, size_t size,
                          r6_enma_exports_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    if (!bytes || !out || size < 24u ||
        r6_memcmp(bytes, enma_exports_magic,
                  sizeof(enma_exports_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->count = r6_u32(bytes, 12);
    if (out->count != R6_ENMA_EXPORT_COUNT) {
        return R6_ERR_FORMAT;
    }
    out->strings_off = r6_u32(bytes, 16);
    out->strings_size = r6_u32(bytes, 20);
    if (out->strings_off != 24u + out->count * 4u ||
        !out->strings_size ||
        (uint64_t)out->strings_off + out->strings_size != size) {
        r6_memset(out, 0, sizeof(*out));
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_enma_exports_parse(const void *data, size_t size,
                          r6_enma_exports_header *out) {
    return exports_header(data, size, out);
}

int r6_enma_exports_name(const void *data, size_t size, uint32_t index,
                         char *name, size_t capacity) {
    r6_enma_exports_header header;
    const unsigned char *bytes;
    uint32_t offset;
    uint32_t at;
    uint32_t end;
    int result = exports_header(data, size, &header);
    if (result != R6_OK || index >= header.count || !name || !capacity) {
        return result == R6_OK ? R6_ERR_ARG : result;
    }
    bytes = (const unsigned char *)data;
    offset = r6_u32(bytes, 24u + index * 4u);
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

int r6_enma_exports_find(const void *data, size_t size,
                         const char *name, uint32_t *index) {
    r6_enma_exports_header header;
    const unsigned char *bytes;
    uint32_t length;
    uint32_t at;
    uint32_t end;
    int result = exports_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!name || !index) {
        return R6_ERR_ARG;
    }
    length = (uint32_t)r6_strlen(name);
    if (!length || length > R6_ENMA_EXPORT_NAME_CAP) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    end = header.strings_off + header.strings_size;
    for (at = 0; at < header.count; at++) {
        uint32_t offset = r6_u32(bytes, 24u + at * 4u);
        uint32_t cursor;
        if (offset < header.strings_off || offset >= end) {
            return R6_ERR_FORMAT;
        }
        cursor = offset;
        while (cursor < end && bytes[cursor]) {
            cursor++;
        }
        if (cursor == end) {
            return R6_ERR_FORMAT;
        }
        if (cursor - offset == length &&
            r6_memcmp(bytes + offset, name, length) == 0) {
            *index = at;
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}
