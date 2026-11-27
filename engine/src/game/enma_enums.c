/* Bounded reader for exported Enma enum domains. No DLL loading or allocation;
 * the host supplies the derived blob and caller buffers. */

#include "r6/r6_enma_enums.h"

#include "core/internal.h"

static const unsigned char enma_enum_magic[8] = {
    'R', '6', 'E', 'M', 'E', 0, 1, 0
};

static int enma_header(const void *data, size_t size,
                       r6_enma_enum_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint64_t arrays_end;
    if (!bytes || !out || size < 24u ||
        r6_memcmp(bytes, enma_enum_magic, sizeof(enma_enum_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->count = r6_u32(bytes, 12);
    if (out->count != R6_ENMA_ENUM_COUNT) {
        return R6_ERR_FORMAT;
    }
    arrays_end = 24u + (uint64_t)out->count * 16u;
    out->strings_off = r6_u32(bytes, 16);
    out->strings_size = r6_u32(bytes, 20);
    if (out->strings_off < arrays_end || !out->strings_size ||
        (uint64_t)out->strings_off + out->strings_size != size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int enma_copy(const unsigned char *bytes,
                     const r6_enma_enum_header *header, uint32_t offset,
                     char *out, size_t capacity) {
    uint32_t end = header->strings_off + header->strings_size;
    uint32_t at;
    if (offset < header->strings_off || offset >= end) {
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

static int enma_row(const void *data, size_t size, uint32_t index,
                    const unsigned char **bytes, r6_enma_enum_header *header,
                    uint32_t *row_off, uint32_t *count, uint32_t *values_off) {
    int result = enma_header(data, size, header);
    uint32_t arrays_end;
    if (result != R6_OK || index >= header->count) {
        return result == R6_OK ? R6_ERR_ARG : result;
    }
    *bytes = (const unsigned char *)data;
    *row_off = 24u + index * 16u;
    *count = r6_u32(*bytes, *row_off + 4u);
    *values_off = r6_u32(*bytes, *row_off + 8u);
    arrays_end = 24u + header->count * 16u;
    if (!*count || *values_off < arrays_end ||
        (uint64_t)*values_off + (uint64_t)*count * 8u > header->strings_off) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_enma_enum_parse(const void *data, size_t size,
                       r6_enma_enum_header *out) {
    return enma_header(data, size, out);
}

int r6_enma_enum_name(const void *data, size_t size, uint32_t index,
                      char *name, size_t capacity) {
    r6_enma_enum_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t count;
    uint32_t values_off;
    int result = enma_row(data, size, index, &bytes, &header, &row_off,
                          &count, &values_off);
    if (result != R6_OK || !name || !capacity) {
        return R6_ERR_ARG;
    }
    return enma_copy(bytes, &header, r6_u32(bytes, row_off), name, capacity);
}

int r6_enma_enum_find_domain(const void *data, size_t size, const char *name,
                             uint32_t *index) {
    r6_enma_enum_header header;
    size_t wanted;
    uint32_t at;
    int result = enma_header(data, size, &header);
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
        char found[R6_ENMA_ENUM_NAME_CAP];
        result = r6_enma_enum_name(data, size, at, found, sizeof(found));
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

int r6_enma_enum_count(const void *data, size_t size, uint32_t index,
                       uint32_t *count) {
    r6_enma_enum_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t values;
    uint32_t values_off;
    int result = enma_row(data, size, index, &bytes, &header, &row_off,
                          &values, &values_off);
    if (result != R6_OK) {
        return result;
    }
    if (!count) {
        return R6_ERR_ARG;
    }
    *count = values;
    return R6_OK;
}

int r6_enma_enum_value(const void *data, size_t size, uint32_t index,
                       uint32_t ordinal, uint32_t *value, char *name,
                       size_t capacity) {
    r6_enma_enum_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t count;
    uint32_t values_off;
    uint32_t at;
    int result = enma_row(data, size, index, &bytes, &header, &row_off,
                          &count, &values_off);
    if (result != R6_OK || !name || !capacity) {
        return R6_ERR_ARG;
    }
    if (ordinal >= count) {
        return R6_ERR_ARG;
    }
    at = values_off + ordinal * 8u;
    if (value) {
        *value = r6_u32(bytes, at + 4u);
    }
    return enma_copy(bytes, &header, r6_u32(bytes, at), name, capacity);
}

int r6_enma_enum_find(const void *data, size_t size, uint32_t index,
                      uint32_t value, char *name, size_t capacity) {
    r6_enma_enum_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t count;
    uint32_t values_off;
    uint32_t at;
    int result = enma_row(data, size, index, &bytes, &header, &row_off,
                          &count, &values_off);
    if (result != R6_OK || !name || !capacity) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < count; at++) {
        uint32_t offset = values_off + at * 8u;
        if (r6_u32(bytes, offset + 4u) == value) {
            return enma_copy(bytes, &header, r6_u32(bytes, offset), name,
                             capacity);
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_enma_enum_find_ordinals(const void *data, size_t size, uint32_t index,
                               uint32_t value, uint32_t *ordinals,
                               uint32_t capacity, uint32_t *count) {
    r6_enma_enum_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t total = 0;
    uint32_t copied = 0;
    uint32_t domain_count;
    uint32_t values_off;
    uint32_t at;
    int result = enma_row(data, size, index, &bytes, &header, &row_off,
                          &domain_count, &values_off);
    if (result != R6_OK) {
        return result;
    }
    if (capacity && !ordinals) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < domain_count; at++) {
        uint32_t offset = values_off + at * 8u;
        if (r6_u32(bytes, offset + 4u) == value) {
            if (copied < capacity) {
                ordinals[copied++] = at;
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
