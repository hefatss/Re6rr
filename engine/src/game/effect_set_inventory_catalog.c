/* Bounds-checked reader for packed stage-effect SET_*.lua inventories. */

#include "r6/r6_effect_set_inventory_catalog.h"

#include "core/internal.h"

enum {
    R6_EFS_HEADER_SIZE = 28,
    R6_EFS_FILE_SIZE = 44,
    R6_EFS_ROW_SIZE = 16,
    R6_EFS_FILES = 300,
    R6_EFS_ROWS = 1899,
    R6_EFS_SOURCE = 501917,
    R6_EFS_MAX_STRING = 128
};

static const unsigned char efs_magic[8] = {
    'R', '6', 'E', 'F', 'S', 0, 1, 0
};

static int efs_header(const void *data, size_t size,
                      r6_effect_set_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_EFS_HEADER_SIZE ||
            r6_memcmp(bytes, efs_magic, sizeof(efs_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_EFS_FILES ||
            r6_u32(bytes, 16) != R6_EFS_ROWS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_EFS_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.row_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_EFS_HEADER_SIZE +
           (size_t)header.file_count * R6_EFS_FILE_SIZE +
           (size_t)header.row_count * R6_EFS_ROW_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t efs_rows_base(void) {
    return R6_EFS_HEADER_SIZE + R6_EFS_FILES * R6_EFS_FILE_SIZE;
}

static size_t efs_strings_base(void) {
    return efs_rows_base() + R6_EFS_ROWS * R6_EFS_ROW_SIZE;
}

static int efs_string(const void *data,
                      const r6_effect_set_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = efs_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_EFS_MAX_STRING || (size_t)offset < base ||
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

static int efs_copy(const void *data,
                    const r6_effect_set_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = efs_string(data, header, offset, length);
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

static int efs_digits(const void *data,
                      const r6_effect_set_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t at;
    if (!length || efs_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    at = bytes[offset] == '-' ? 1u : 0u;
    if (at >= length) {
        return R6_ERR_FORMAT;
    }
    for (; at < length; at++) {
        if (bytes[offset + at] < '0' || bytes[offset + at] > '9') {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int efs_file(const void *data, size_t size, uint32_t index,
                    r6_effect_set_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    r6_effect_set_file_t file;
    size_t at;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_EFS_HEADER_SIZE + (size_t)index * R6_EFS_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.rows || file.row_base > header.row_count ||
            file.rows > header.row_count - file.row_base ||
            file.path_length < 4 ||
            efs_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0 || !file.name_length ||
            efs_string(data, &header, file.name_offset,
                       file.name_length) != R6_OK ||
            efs_digits(data, &header, file.num_offset,
                       file.num_length) != R6_OK ||
            efs_digits(data, &header, file.effect_num_offset,
                       file.effect_num_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int efs_row(const void *data,
                   const r6_effect_set_header_t *header,
                   uint32_t index, r6_effect_set_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_row_t row;
    size_t at = efs_rows_base() + (size_t)index * R6_EFS_ROW_SIZE;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (efs_string(data, header, row.path_offset, row.path_length) != R6_OK ||
            efs_string(data, header, row.model_offset,
                       row.model_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_effect_set_parse(const void *data, size_t size,
                        r6_effect_set_header_t *out) {
    r6_effect_set_header_t header;
    r6_effect_set_file_t file;
    r6_effect_set_row_t row;
    uint32_t source = 0;
    uint32_t rows = 0;
    uint32_t at;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = efs_file(data, size, at, &file);
        if (result != R6_OK || file.row_base != rows) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        rows += file.rows;
    }
    if (source != header.source_bytes || rows != header.row_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = efs_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_effect_set_file(const void *data, size_t size, uint32_t index,
                       r6_effect_set_file_t *out) {
    return efs_file(data, size, index, out);
}

int r6_effect_set_path(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    r6_effect_set_file_t file;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = efs_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return efs_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_effect_set_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    r6_effect_set_file_t file;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = efs_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return efs_copy(data, &header, file.name_offset, file.name_length,
                    out, capacity);
}

int r6_effect_set_num(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    r6_effect_set_file_t file;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = efs_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return efs_copy(data, &header, file.num_offset, file.num_length,
                    out, capacity);
}

int r6_effect_set_effect_num(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    r6_effect_set_file_t file;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = efs_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return efs_copy(data, &header, file.effect_num_offset,
                    file.effect_num_length, out, capacity);
}

int r6_effect_set_row(const void *data, size_t size, uint32_t index,
                      r6_effect_set_row_t *out) {
    r6_effect_set_header_t header;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return efs_row(data, &header, index, out);
}

int r6_effect_set_row_path(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    r6_effect_set_row_t row;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = efs_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return efs_copy(data, &header, row.path_offset, row.path_length,
                    out, capacity);
}

int r6_effect_set_row_model(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_effect_set_header_t header;
    r6_effect_set_row_t row;
    int result = efs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = efs_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return efs_copy(data, &header, row.model_offset, row.model_length,
                    out, capacity);
}
