/* Bounds-checked reader for the packed NeonColor row inventory. */

#include "r6/r6_neon_color_catalog.h"

#include "core/internal.h"

enum {
    R6_NEO_HEADER_SIZE = 48,
    R6_NEO_ROW_SIZE = 32,
    R6_NEO_ROWS = 6,
    R6_NEO_LINES = 31,
    R6_NEO_SOURCE = 1180,
    R6_NEO_FIRST_LINE = 9,
    R6_NEO_MAX_STRING = 96
};

static const unsigned char neo_magic[8] = {
    'R', '6', 'N', 'E', 'O', 0, 1, 0
};

static int neo_header(const void *data, size_t size, r6_neon_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_neon_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_NEO_HEADER_SIZE ||
            r6_memcmp(bytes, neo_magic, sizeof(neo_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_NEO_ROWS ||
            r6_u32(bytes, 20) != R6_NEO_LINES || !r6_u32(bytes, 24) ||
            r6_u32(bytes, 28) != R6_NEO_SOURCE ||
            r6_u32(bytes, 32) != R6_NEO_ROWS || r6_u32(bytes, 36) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.row_count = R6_NEO_ROWS;
    header.line_count = R6_NEO_LINES;
    header.string_size = r6_u32(bytes, 24);
    header.source_bytes = r6_u32(bytes, 28);
    header.comment_rows = r6_u32(bytes, 32);
    header.reserved = 0u;
    header.path_offset = r6_u32(bytes, 40);
    header.path_length = r6_u32(bytes, 44);
    base = R6_NEO_HEADER_SIZE + R6_NEO_ROWS * R6_NEO_ROW_SIZE +
           header.string_size;
    if (base != size || header.path_length < 5) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t neo_strings_base(void) {
    return R6_NEO_HEADER_SIZE + R6_NEO_ROWS * R6_NEO_ROW_SIZE;
}

static int neo_string(const void *data,
                      const r6_neon_header_t *header,
                      uint32_t offset, uint32_t length, int digits) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = neo_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_NEO_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (digits) {
            if ((value < '0' || value > '9') && value != '.') {
                return R6_ERR_FORMAT;
            }
        } else if (value < 0x20u || value > 0x7eu) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int neo_copy(const void *data,
                    const r6_neon_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = neo_string(data, header, offset, length, 0);
    if (result != R6_OK) {
        return result;
    }
    if (!out || !capacity || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int neo_path(const void *data, size_t size, char *out,
                    size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_neon_header_t header;
    int result = neo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (neo_string(data, &header, header.path_offset,
                   header.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + header.path_offset + header.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    if (!out || !capacity ||
            (size_t)header.path_length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + header.path_offset, header.path_length);
    out[header.path_length] = 0;
    return R6_OK;
}

static int neo_row(const void *data,
                   const r6_neon_header_t *header,
                   uint32_t index, r6_neon_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_neon_row_t row;
    uint32_t at;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + R6_NEO_HEADER_SIZE +
              (size_t)index * R6_NEO_ROW_SIZE, sizeof(row));
    if (row.has_comment != 1u ||
            row.line != R6_NEO_FIRST_LINE + index) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < 3; at++) {
        if (neo_string(data, header, row.token_offset[at],
                       row.token_length[at], 1) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_neon_parse(const void *data, size_t size, r6_neon_header_t *out) {
    r6_neon_header_t header;
    r6_neon_row_t row;
    char text[R6_NEO_MAX_STRING + 1];
    uint32_t at;
    uint32_t slot;
    int result = neo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out || neo_path(data, size, text, sizeof(text)) != R6_OK) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.row_count; at++) {
        result = neo_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
        for (slot = 0; slot < 3; slot++) {
            if (neo_copy(data, &header, row.token_offset[slot],
                         row.token_length[slot], text,
                         sizeof(text)) != R6_OK) {
                return R6_ERR_FORMAT;
            }
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_neon_path(const void *data, size_t size, char *out, size_t capacity) {
    return neo_path(data, size, out, capacity);
}

int r6_neon_row(const void *data, size_t size, uint32_t index,
                r6_neon_row_t *out) {
    r6_neon_header_t header;
    int result = neo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return neo_row(data, &header, index, out);
}

int r6_neon_token(const void *data, size_t size, uint32_t index,
                  uint32_t slot, char *out, size_t capacity) {
    r6_neon_header_t header;
    r6_neon_row_t row;
    int result = neo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (slot >= 3u) {
        return R6_ERR_ARG;
    }
    result = neo_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return neo_copy(data, &header, row.token_offset[slot],
                    row.token_length[slot], out, capacity);
}
