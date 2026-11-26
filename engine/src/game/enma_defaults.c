/* Bounded reader for the recovered SetDefault constant writes. No DLL loading,
 * allocation or host memory access: the caller supplies the derived blob. */

#include "r6/r6_enma_defaults.h"

#include "core/internal.h"

static const unsigned char enma_defaults_magic[8] = {
    'R', '6', 'E', 'D', 'F', 0, 1, 0
};

static int defaults_header(const void *data, size_t size,
                           r6_enma_defaults_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    if (!bytes || !out || size < 32u ||
        r6_memcmp(bytes, enma_defaults_magic,
                  sizeof(enma_defaults_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->count = r6_u32(bytes, 12);
    out->fields_off = r6_u32(bytes, 16);
    out->data_off = r6_u32(bytes, 20);
    out->strings_off = r6_u32(bytes, 24);
    out->strings_size = r6_u32(bytes, 28);
    if (out->count != R6_ENMA_DEFAULT_STRUCTS ||
        out->fields_off != 32u + out->count * 16u ||
        out->data_off < out->fields_off ||
        out->strings_off < out->data_off || !out->strings_size ||
        (uint64_t)out->strings_off + out->strings_size != size) {
        r6_memset(out, 0, sizeof(*out));
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int defaults_name(const unsigned char *bytes,
                         const r6_enma_defaults_header *header,
                         uint32_t offset, char *out, size_t capacity) {
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

static int defaults_row(const void *data, size_t size, uint32_t index,
                        const unsigned char **bytes,
                        r6_enma_defaults_header *header, uint32_t *row_off,
                        uint32_t *field_count) {
    int result = defaults_header(data, size, header);
    if (result != R6_OK || index >= header->count) {
        return result == R6_OK ? R6_ERR_ARG : result;
    }
    *bytes = (const unsigned char *)data;
    *row_off = 32u + index * 16u;
    *field_count = r6_u32(*bytes, *row_off + 8u);
    if (!*field_count ||
        (uint64_t)header->fields_off + (uint64_t)*field_count * 16u >
            header->data_off) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_enma_defaults_parse(const void *data, size_t size,
                           r6_enma_defaults_header *out) {
    return defaults_header(data, size, out);
}

int r6_enma_defaults_struct(const void *data, size_t size, uint32_t index,
                            char *name, size_t capacity,
                            uint32_t *max_written, uint32_t *field_count) {
    r6_enma_defaults_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t count;
    int result = defaults_row(data, size, index, &bytes, &header, &row_off,
                              &count);
    if (result != R6_OK || !name || !capacity) {
        return R6_ERR_ARG;
    }
    result = defaults_name(bytes, &header, r6_u32(bytes, row_off), name,
                           capacity);
    if (result != R6_OK) {
        return result;
    }
    if (max_written) {
        *max_written = r6_u32(bytes, row_off + 4u);
    }
    if (field_count) {
        *field_count = count;
    }
    return R6_OK;
}

int r6_enma_defaults_find(const void *data, size_t size, const char *name,
                          uint32_t *index) {
    r6_enma_defaults_header header;
    size_t wanted;
    uint32_t at;
    int result = defaults_header(data, size, &header);
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
        char found[R6_ENMA_DEFAULT_NAME_CAP];
        result = r6_enma_defaults_struct(data, size, at, found,
                                         sizeof(found), NULL, NULL);
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

int r6_enma_defaults_field(const void *data, size_t size, uint32_t index,
                           uint32_t field, uint32_t *offset,
                           uint32_t *byte_count, void *out, size_t capacity) {
    r6_enma_defaults_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t count;
    uint32_t base = 0;
    uint32_t at;
    uint32_t row;
    uint32_t data_off;
    uint32_t length;
    int result = defaults_row(data, size, index, &bytes, &header, &row_off,
                              &count);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < index; at++) {
        base += r6_u32(bytes, 32u + at * 16u + 8u);
    }
    if (field >= count) {
        return R6_ERR_ARG;
    }
    row = header.fields_off + (base + field) * 16u;
    if ((uint64_t)row + 16u > header.data_off) {
        return R6_ERR_FORMAT;
    }
    data_off = r6_u32(bytes, row + 8u);
    length = r6_u32(bytes, row + 4u);
    if (data_off < header.data_off || !length ||
        (uint64_t)data_off + length > header.strings_off) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        if (capacity < length) {
            return R6_ERR_BUFFER;
        }
        r6_memcpy(out, bytes + data_off, length);
    }
    if (offset) {
        *offset = r6_u32(bytes, row);
    }
    if (byte_count) {
        *byte_count = length;
    }
    return R6_OK;
}
