/* Bounds-checked reader for packed Zenichi name-plate facts. */

#include "r6/r6_zenichi_config_catalog.h"

#include "core/internal.h"

enum {
    R6_ZNC_HEADER_SIZE = 24,
    R6_ZNC_ROW_SIZE = 20,
    R6_ZNC_ROW_COUNT = 276,
    R6_ZNC_SOURCE_SIZE = 30209
};

static const unsigned char znc_magic[8] = {
    'R', '6', 'Z', 'N', 'C', 0, 1, 0
};

static int znc_header(const void *data, size_t size,
                      r6_zenichi_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_zenichi_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_ZNC_HEADER_SIZE ||
            r6_memcmp(bytes, znc_magic, sizeof(znc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_ZNC_ROW_COUNT ||
            !r6_u32(bytes, 16) || r6_u32(bytes, 20) != R6_ZNC_SOURCE_SIZE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.row_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.source_size = r6_u32(bytes, 20);
    base = R6_ZNC_HEADER_SIZE + (size_t)header.row_count * R6_ZNC_ROW_SIZE;
    if (base > (size_t)-1 - header.string_size ||
            base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int znc_name(const void *data, const r6_zenichi_header_t *header,
                    uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = R6_ZNC_HEADER_SIZE + (size_t)header->row_count *
                                       R6_ZNC_ROW_SIZE;
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > 64 || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        if (bytes[(size_t)offset + at] >= 0x80u) {
            return R6_ERR_FORMAT;
        }
    }
    if (bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int znc_row(const void *data, size_t size, uint32_t index,
                   r6_zenichi_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_zenichi_header_t header;
    r6_zenichi_row_t row;
    size_t at;
    int result = znc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.row_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_ZNC_HEADER_SIZE + (size_t)index * R6_ZNC_ROW_SIZE;
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.item != index + 1u || row.variation < 1u || row.variation > 6u ||
            row.layout > 1u ||
            znc_name(data, &header, row.name_offset, row.name_length) !=
                R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_zenichi_parse(const void *data, size_t size,
                     r6_zenichi_header_t *out) {
    r6_zenichi_header_t header;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = znc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_zenichi_row(const void *data, size_t size, uint32_t index,
                   r6_zenichi_row_t *out) {
    return znc_row(data, size, index, out);
}

int r6_zenichi_find_id(const void *data, size_t size, uint32_t item,
                       r6_zenichi_row_t *out) {
    r6_zenichi_header_t header;
    r6_zenichi_row_t row;
    uint32_t at;
    int result = znc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.row_count; at++) {
        result = znc_row(data, size, at, &row);
        if (result != R6_OK) {
            return result;
        }
        if (row.item == item) {
            r6_memcpy(out, &row, sizeof(row));
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_zenichi_name(const void *data, size_t size, uint32_t index,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_zenichi_header_t header;
    r6_zenichi_row_t row;
    int result = znc_row(data, size, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)row.name_length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    result = znc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    (void)header;
    r6_memcpy(out, bytes + row.name_offset, row.name_length);
    out[row.name_length] = 0;
    return R6_OK;
}
