/* Bounds-checked reader for packed custom-frame id/name facts. */

#include "r6/r6_custom_frame_catalog.h"

#include "core/internal.h"

enum {
    R6_CFM_HEADER_SIZE = 32,
    R6_CFM_ROW_SIZE = 36,
    R6_CFM_FUNCTION_SIZE = 8,
    R6_CFM_ROWS = 183,
    R6_CFM_NAMES = 732,
    R6_CFM_FUNCTIONS = 6,
    R6_CFM_SOURCE_SIZE = 26386,
    R6_CFM_NAME_LENGTH = 21
};

static const unsigned char cfm_magic[8] = {
    'R', '6', 'C', 'F', 'M', 0, 1, 0
};

static int cfm_header(const void *data, size_t size,
                      r6_custom_frame_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_custom_frame_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_CFM_HEADER_SIZE ||
            r6_memcmp(bytes, cfm_magic, sizeof(cfm_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_CFM_ROWS ||
            r6_u32(bytes, 16) != R6_CFM_NAMES ||
            r6_u32(bytes, 20) != R6_CFM_FUNCTIONS ||
            !r6_u32(bytes, 24) || r6_u32(bytes, 28) != R6_CFM_SOURCE_SIZE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.row_count = r6_u32(bytes, 12);
    header.name_count = r6_u32(bytes, 16);
    header.function_count = r6_u32(bytes, 20);
    header.string_size = r6_u32(bytes, 24);
    header.source_size = r6_u32(bytes, 28);
    base = R6_CFM_HEADER_SIZE +
           (size_t)header.row_count * R6_CFM_ROW_SIZE +
           (size_t)header.function_count * R6_CFM_FUNCTION_SIZE;
    if (base > (size_t)-1 - header.string_size ||
            base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t cfm_strings_base(const r6_custom_frame_header_t *header) {
    return R6_CFM_HEADER_SIZE +
           (size_t)header->row_count * R6_CFM_ROW_SIZE +
           (size_t)header->function_count * R6_CFM_FUNCTION_SIZE;
}

static int cfm_string(const void *data, const r6_custom_frame_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = cfm_strings_base(header);
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

static int cfm_row(const void *data, size_t size, uint32_t index,
                   r6_custom_frame_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_custom_frame_header_t header;
    r6_custom_frame_row_t row;
    size_t at;
    int result = cfm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.row_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_CFM_HEADER_SIZE + (size_t)index * R6_CFM_ROW_SIZE;
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.id != index + 1u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < 4; at++) {
        size_t offset = row.name_offset[at];
        if (row.name_length[at] != R6_CFM_NAME_LENGTH ||
                cfm_string(data, &header, row.name_offset[at],
                           row.name_length[at]) != R6_OK ||
                r6_memcmp(bytes + offset, "cmn_cf_", 7) != 0 ||
                r6_memcmp(bytes + offset + R6_CFM_NAME_LENGTH - 4, ".nut",
                          4) != 0) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int cfm_function(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_custom_frame_header_t header;
    uint32_t offset;
    uint32_t length;
    size_t at;
    int result = cfm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.function_count) {
        return R6_ERR_ARG;
    }
    at = R6_CFM_HEADER_SIZE +
         (size_t)header.row_count * R6_CFM_ROW_SIZE +
         (size_t)index * R6_CFM_FUNCTION_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    result = cfm_string(data, &header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_custom_frame_parse(const void *data, size_t size,
                          r6_custom_frame_header_t *out) {
    r6_custom_frame_header_t header;
    r6_custom_frame_row_t row;
    uint32_t at;
    int result = cfm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.row_count; at++) {
        result = cfm_row(data, size, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.function_count; at++) {
        char name[64];
        result = cfm_function(data, size, at, name, sizeof(name));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_custom_frame_row(const void *data, size_t size, uint32_t index,
                        r6_custom_frame_row_t *out) {
    return cfm_row(data, size, index, out);
}

int r6_custom_frame_texture(const void *data, size_t size, uint32_t index,
                            uint32_t slot, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_custom_frame_row_t row;
    int result = cfm_row(data, size, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot >= 4) {
        return R6_ERR_ARG;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)row.name_length[slot] + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + row.name_offset[slot], row.name_length[slot]);
    out[row.name_length[slot]] = 0;
    return R6_OK;
}

int r6_custom_frame_function(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity) {
    return cfm_function(data, size, index, out, capacity);
}
