/* Bounds-checked reader for packed DISTCLIP.lua inventories. */

#include "r6/r6_distclip_catalog.h"

#include "core/internal.h"

enum {
    R6_DCL_HEADER_SIZE = 28,
    R6_DCL_FILE_SIZE = 32,
    R6_DCL_ROW_SIZE = 12,
    R6_DCL_FILES = 395,
    R6_DCL_ROWS = 3950,
    R6_DCL_SOURCE = 83284,
    R6_DCL_MAX_STRING = 128,
    R6_DCL_MAX_VALUE = 50000
};

static const unsigned char dcl_magic[8] = {
    'R', '6', 'D', 'C', 'L', 0, 1, 0
};

static const char *const dcl_keys[10] = {
    "ROAD", "ONRD", "LONG", "NEAR", "LODM", "CAST", "BACK", "REFC", "REFR",
    "RFBG"
};

static int dcl_header(const void *data, size_t size,
                      r6_distclip_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_distclip_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_DCL_HEADER_SIZE ||
            r6_memcmp(bytes, dcl_magic, sizeof(dcl_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_DCL_FILES ||
            r6_u32(bytes, 16) != R6_DCL_ROWS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_DCL_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.row_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_DCL_HEADER_SIZE +
           (size_t)header.file_count * R6_DCL_FILE_SIZE +
           (size_t)header.row_count * R6_DCL_ROW_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t dcl_rows_base(void) {
    return R6_DCL_HEADER_SIZE + R6_DCL_FILES * R6_DCL_FILE_SIZE;
}

static size_t dcl_strings_base(void) {
    return dcl_rows_base() + R6_DCL_ROWS * R6_DCL_ROW_SIZE;
}

static int dcl_string(const void *data,
                      const r6_distclip_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = dcl_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_DCL_MAX_STRING || (size_t)offset < base ||
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

static int dcl_copy(const void *data,
                    const r6_distclip_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = dcl_string(data, header, offset, length);
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

static int dcl_table_name(const unsigned char *bytes,
                          const r6_distclip_header_t *header,
                          uint32_t offset, uint32_t length) {
    if (dcl_string(bytes, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (length == 21 &&
            r6_memcmp(bytes + offset, "DEFAULT_CLIP_DISTANCE", 21) == 0) {
        return R6_OK;
    }
    if (length == 16 &&
            r6_memcmp(bytes + offset, "CLIP_DISTANCE_", 14) == 0 &&
            bytes[offset + 14] >= '0' && bytes[offset + 14] <= '9' &&
            bytes[offset + 15] >= '0' && bytes[offset + 15] <= '9') {
        return R6_OK;
    }
    return R6_ERR_FORMAT;
}

static int dcl_file(const void *data, size_t size, uint32_t index,
                    r6_distclip_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_distclip_header_t header;
    r6_distclip_file_t file;
    size_t at;
    int result = dcl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_DCL_HEADER_SIZE + (size_t)index * R6_DCL_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.lines || file.rows != 10u ||
            file.row_base > header.row_count ||
            file.rows > header.row_count - file.row_base ||
            file.path_length < 4 ||
            dcl_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0 ||
            dcl_table_name(bytes, &header, file.table_offset,
                           file.table_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int dcl_row(const void *data,
                   const r6_distclip_header_t *header,
                   uint32_t index, r6_distclip_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_distclip_row_t row;
    size_t at = dcl_rows_base() + (size_t)index * R6_DCL_ROW_SIZE;
    unsigned int key;
    int known = 0;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (dcl_string(data, header, row.key_offset, row.key_length) != R6_OK ||
            row.value > R6_DCL_MAX_VALUE) {
        return R6_ERR_FORMAT;
    }
    for (key = 0; key < 10u; key++) {
        size_t length = r6_strlen(dcl_keys[key]);
        if (row.key_length == length &&
                r6_memcmp(bytes + row.key_offset, dcl_keys[key], length) == 0) {
            known = 1;
            break;
        }
    }
    if (!known) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_distclip_parse(const void *data, size_t size,
                      r6_distclip_header_t *out) {
    r6_distclip_header_t header;
    r6_distclip_file_t file;
    r6_distclip_row_t row;
    uint32_t source = 0;
    uint32_t rows = 0;
    uint32_t at;
    int result = dcl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = dcl_file(data, size, at, &file);
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
        result = dcl_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_distclip_file(const void *data, size_t size, uint32_t index,
                     r6_distclip_file_t *out) {
    return dcl_file(data, size, index, out);
}

int r6_distclip_path(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_distclip_header_t header;
    r6_distclip_file_t file;
    int result = dcl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = dcl_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return dcl_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_distclip_table(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_distclip_header_t header;
    r6_distclip_file_t file;
    int result = dcl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = dcl_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return dcl_copy(data, &header, file.table_offset, file.table_length,
                    out, capacity);
}

int r6_distclip_row(const void *data, size_t size, uint32_t index,
                    r6_distclip_row_t *out) {
    r6_distclip_header_t header;
    int result = dcl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return dcl_row(data, &header, index, out);
}

int r6_distclip_row_key(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_distclip_header_t header;
    r6_distclip_row_t row;
    int result = dcl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = dcl_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return dcl_copy(data, &header, row.key_offset, row.key_length,
                    out, capacity);
}

int r6_distclip_row_value(const void *data, size_t size, uint32_t index,
                          uint32_t *out) {
    r6_distclip_header_t header;
    r6_distclip_row_t row;
    int result = dcl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = dcl_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    *out = row.value;
    return R6_OK;
}
