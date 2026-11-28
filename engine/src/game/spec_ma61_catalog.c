/* Bounds-checked reader for packed MA61 specification rows. */

#include "r6/r6_spec_ma61_catalog.h"

#include "core/internal.h"

enum {
    R6_MA6_HEADER_SIZE = 48,
    R6_MA6_ROW_SIZE = 28,
    R6_MA6_ROWS = 373,
    R6_MA6_SOURCE = 139729,
    R6_MA6_LINES = 3000,
    R6_MA6_TABLE_START = 12,
    R6_MA6_TABLE_END = 387,
    R6_MA6_MAX_STRING = 96
};

static const unsigned char ma6_magic[8] = {
    'R', '6', 'M', 'A', '6', 0, 1, 0
};

static int ma6_header(const void *data, size_t size,
                      r6_spec_ma61_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_spec_ma61_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_MA6_HEADER_SIZE ||
            r6_memcmp(bytes, ma6_magic, sizeof(ma6_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_MA6_ROWS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_MA6_SOURCE ||
            r6_u32(bytes, 28) != R6_MA6_LINES ||
            r6_u32(bytes, 32) != R6_MA6_TABLE_START ||
            r6_u32(bytes, 36) != R6_MA6_TABLE_END) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.row_count = R6_MA6_ROWS;
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    header.lines = r6_u32(bytes, 28);
    header.table_start = r6_u32(bytes, 32);
    header.table_end = r6_u32(bytes, 36);
    header.path_offset = r6_u32(bytes, 40);
    header.path_length = r6_u32(bytes, 44);
    base = R6_MA6_HEADER_SIZE +
           (size_t)header.row_count * R6_MA6_ROW_SIZE + header.string_size;
    if (base != size || header.path_length < 4) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t ma6_strings_base(void) {
    return R6_MA6_HEADER_SIZE + R6_MA6_ROWS * R6_MA6_ROW_SIZE;
}

static int ma6_string(const void *data,
                      const r6_spec_ma61_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = ma6_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_MA6_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0 ||
            (!allow_empty && !length)) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (value < 0x20u || value > 0x7eu) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int ma6_copy(const void *data,
                    const r6_spec_ma61_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = ma6_string(data, header, offset, length, 1);
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

static int ma6_path(const void *data, size_t size, char *out,
                    size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_spec_ma61_header_t header;
    int result = ma6_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (ma6_string(data, &header, header.path_offset,
                   header.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + header.path_offset + header.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    return ma6_copy(data, &header, header.path_offset, header.path_length,
                    out, capacity);
}

static int ma6_row(const void *data,
                   const r6_spec_ma61_header_t *header,
                   uint32_t index, r6_spec_ma61_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_spec_ma61_row_t row;
    size_t at = R6_MA6_HEADER_SIZE + (size_t)index * R6_MA6_ROW_SIZE;
    uint32_t cursor;
    unsigned char first;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.kind > 3u || row.comment > 1u ||
            row.line <= header->table_start || row.line >= header->table_end ||
            ma6_string(data, header, row.key_offset, row.key_length, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    first = bytes[row.key_offset];
    if (!((first >= 'A' && first <= 'Z') ||
          (first >= 'a' && first <= 'z') || first == '_')) {
        return R6_ERR_FORMAT;
    }
    for (cursor = 0; cursor < row.key_length; cursor++) {
        unsigned char value = bytes[row.key_offset + cursor];
        if (!((value >= 'A' && value <= 'Z') ||
              (value >= 'a' && value <= 'z') ||
              (value >= '0' && value <= '9') || value == '_')) {
            return R6_ERR_FORMAT;
        }
    }
    if (row.kind == 3u) {
        if (row.literal_length) {
            return R6_ERR_FORMAT;
        }
    } else if (ma6_string(data, header, row.literal_offset,
                          row.literal_length, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (row.kind == 0u || row.kind == 1u) {
        int digits = 0;
        int dot = 0;
        for (cursor = 0; cursor < row.literal_length; cursor++) {
            unsigned char value = bytes[row.literal_offset + cursor];
            if (value >= '0' && value <= '9') {
                digits++;
            } else if (value == '.' && !dot) {
                dot++;
            } else if (value != '-') {
                return R6_ERR_FORMAT;
            }
        }
        if (!digits || (row.kind == 1u && !dot) ||
                (row.kind == 0u && dot)) {
            return R6_ERR_FORMAT;
        }
    } else if (row.kind == 2u) {
        if (row.literal_length < 2 ||
                bytes[row.literal_offset] != '"' ||
                bytes[row.literal_offset + row.literal_length - 1] != '"') {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_spec_ma61_parse(const void *data, size_t size,
                       r6_spec_ma61_header_t *out) {
    r6_spec_ma61_header_t header;
    r6_spec_ma61_row_t row;
    char text[R6_MA6_MAX_STRING + 1];
    uint32_t kinds[4] = {0, 0, 0, 0};
    uint32_t comments = 0;
    uint32_t at;
    int result = ma6_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if (ma6_path(data, size, text, sizeof(text)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = ma6_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
        kinds[row.kind]++;
        comments += row.comment;
    }
    if (kinds[0] != 317u || kinds[1] != 2u || kinds[2] != 38u ||
            kinds[3] != 16u || comments != 46u) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_spec_ma61_path(const void *data, size_t size, char *out,
                      size_t capacity) {
    return ma6_path(data, size, out, capacity);
}

int r6_spec_ma61_row(const void *data, size_t size, uint32_t index,
                     r6_spec_ma61_row_t *out) {
    r6_spec_ma61_header_t header;
    int result = ma6_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return ma6_row(data, &header, index, out);
}

int r6_spec_ma61_key(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    r6_spec_ma61_header_t header;
    r6_spec_ma61_row_t row;
    int result = ma6_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ma6_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ma6_copy(data, &header, row.key_offset, row.key_length,
                    out, capacity);
}

int r6_spec_ma61_literal(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    r6_spec_ma61_header_t header;
    r6_spec_ma61_row_t row;
    int result = ma6_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ma6_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ma6_copy(data, &header, row.literal_offset, row.literal_length,
                    out, capacity);
}
