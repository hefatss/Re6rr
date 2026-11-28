/* Bounds-checked reader for packed setting default rows. */

#include "r6/r6_setting_default_catalog.h"

#include "core/internal.h"

enum {
    R6_STD_HEADER_SIZE = 32,
    R6_STD_FILE_SIZE = 16,
    R6_STD_ROW_SIZE = 20,
    R6_STD_ROWS = 13,
    R6_STD_ACTIVE = 12,
    R6_STD_SOURCE = 1343,
    R6_STD_LINES = 34,
    R6_STD_MAX_STRING = 96
};

static const unsigned char std_magic[8] = {
    'R', '6', 'S', 'T', 'D', 0, 1, 0
};

static int std_header(const void *data, size_t size,
                      r6_setting_default_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_setting_default_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_STD_HEADER_SIZE ||
            r6_memcmp(bytes, std_magic, sizeof(std_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_STD_ROWS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_STD_SOURCE ||
            r6_u32(bytes, 28) != R6_STD_LINES) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.row_count = R6_STD_ROWS;
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    header.lines = r6_u32(bytes, 28);
    base = R6_STD_HEADER_SIZE + R6_STD_FILE_SIZE +
           R6_STD_ROWS * R6_STD_ROW_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t std_rows_base(void) {
    return R6_STD_HEADER_SIZE + R6_STD_FILE_SIZE;
}

static size_t std_strings_base(void) {
    return std_rows_base() + R6_STD_ROWS * R6_STD_ROW_SIZE;
}

static int std_string(const void *data,
                      const r6_setting_default_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = std_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_STD_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
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

static int std_copy(const void *data,
                    const r6_setting_default_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = std_string(data, header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int std_path(const void *data, size_t size, char *out,
                    size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_setting_default_header_t header;
    uint32_t offset;
    uint32_t length;
    int result = std_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    offset = r6_u32(bytes, R6_STD_HEADER_SIZE);
    length = r6_u32(bytes, R6_STD_HEADER_SIZE + 4);
    if (std_string(data, &header, offset, length) != R6_OK ||
            r6_memcmp(bytes + offset + length - 4, ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    return std_copy(data, &header, offset, length, out, capacity);
}

static int std_row(const void *data,
                   const r6_setting_default_header_t *header,
                   uint32_t index, r6_setting_default_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_setting_default_row_t row;
    size_t at = std_rows_base() + (size_t)index * R6_STD_ROW_SIZE;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.active > 1u || row.name_length < 4 ||
            r6_memcmp(bytes + row.name_offset, "m_", 2) != 0 ||
            std_string(data, header, row.name_offset, row.name_length) != R6_OK ||
            std_string(data, header, row.value_offset, row.value_length) != R6_OK ||
            (r6_memcmp(bytes + row.value_offset, "SettingConst.", 13) != 0 &&
             r6_memcmp(bytes + row.value_offset, "0x", 2) != 0)) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_setting_default_parse(const void *data, size_t size,
                             r6_setting_default_header_t *out) {
    r6_setting_default_header_t header;
    r6_setting_default_row_t row;
    char text[R6_STD_MAX_STRING + 1];
    uint32_t active = 0;
    uint32_t at;
    int result = std_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if (std_path(data, size, text, sizeof(text)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = std_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
        active += row.active;
    }
    if (active != R6_STD_ACTIVE) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_setting_default_path(const void *data, size_t size, char *out,
                            size_t capacity) {
    r6_setting_default_header_t header;
    int result = std_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return std_path(data, size, out, capacity);
}

int r6_setting_default_row(const void *data, size_t size, uint32_t index,
                           r6_setting_default_row_t *out) {
    r6_setting_default_header_t header;
    int result = std_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return std_row(data, &header, index, out);
}

int r6_setting_default_name(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity) {
    r6_setting_default_header_t header;
    r6_setting_default_row_t row;
    int result = std_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = std_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return std_copy(data, &header, row.name_offset, row.name_length,
                    out, capacity);
}

int r6_setting_default_value(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity) {
    r6_setting_default_header_t header;
    r6_setting_default_row_t row;
    int result = std_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = std_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return std_copy(data, &header, row.value_offset, row.value_length,
                    out, capacity);
}
