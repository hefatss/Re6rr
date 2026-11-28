/* Bounds-checked reader for the packed vinyl selector inventory. */

#include "r6/r6_vinyl_select_catalog.h"

#include "core/internal.h"

enum {
    R6_VSL_HEADER_SIZE = 44,
    R6_VSL_FILE_SIZE = 16,
    R6_VSL_ROW_SIZE = 12,
    R6_VSL_FILES = 149,
    R6_VSL_ROWS = 7450,
    R6_VSL_SOURCE = 722358,
    R6_VSL_LINES = 93,
    R6_VSL_ID_MIN = 59,
    R6_VSL_ID_MAX = 108,
    R6_VSL_ROWS_PER_FILE = 50,
    R6_VSL_MAX_STRING = 96
};

static const unsigned char vsl_magic[8] = {
    'R', '6', 'V', 'S', 'L', 0, 1, 0
};

static size_t vsl_files_base(void) {
    return R6_VSL_HEADER_SIZE;
}

static size_t vsl_rows_base(void) {
    return vsl_files_base() + R6_VSL_FILES * R6_VSL_FILE_SIZE;
}

static size_t vsl_strings_base(void) {
    return vsl_rows_base() + R6_VSL_ROWS * R6_VSL_ROW_SIZE;
}

static int vsl_header(const void *data, size_t size, r6_vsl_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_vsl_header_t header;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_VSL_HEADER_SIZE ||
            r6_memcmp(bytes, vsl_magic, sizeof(vsl_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_VSL_FILES ||
            r6_u32(bytes, 16) != R6_VSL_ROWS ||
            r6_u32(bytes, 20) != R6_VSL_SOURCE ||
            r6_u32(bytes, 24) != R6_VSL_LINES ||
            r6_u32(bytes, 28) != R6_VSL_ID_MIN ||
            r6_u32(bytes, 32) != R6_VSL_ID_MAX || !r6_u32(bytes, 36) ||
            r6_u32(bytes, 40) != 0u ||
            vsl_strings_base() + r6_u32(bytes, 36) != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_VSL_FILES;
    header.row_count = R6_VSL_ROWS;
    header.source_bytes = R6_VSL_SOURCE;
    header.line_count = R6_VSL_LINES;
    header.id_min = R6_VSL_ID_MIN;
    header.id_max = R6_VSL_ID_MAX;
    header.string_size = r6_u32(bytes, 36);
    header.reserved = 0u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int vsl_span(const void *data, const r6_vsl_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = vsl_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_VSL_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (digits) {
            if (value < '0' || value > '9') {
                return R6_ERR_FORMAT;
            }
        } else if (value < 0x20u || value > 0x7eu) {
            return R6_ERR_FORMAT;
        }
    }
    if (!out) {
        return R6_OK;
    }
    if (!capacity || (size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int vsl_file_at(const void *data, size_t size, uint32_t index,
                       r6_vsl_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_vsl_header_t header;
    r6_vsl_file_t file;
    char name[R6_VSL_MAX_STRING + 1];
    int result;
    if (vsl_header(data, size, &header) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + vsl_files_base() +
              (size_t)index * R6_VSL_FILE_SIZE, sizeof(file));
    result = vsl_span(data, &header, file.name_offset, file.name_length,
                      0, name, sizeof(name));
    if (result != R6_OK) {
        return result;
    }
    if (file.name_length < 19u ||
            r6_memcmp(name, "getVinylSelect_", 15) != 0 ||
            r6_memcmp(name + file.name_length - 4, ".lua", 4) != 0 ||
            !file.size ||
            file.row_base != index * R6_VSL_ROWS_PER_FILE) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int vsl_row_at(const void *data, const r6_vsl_header_t *header,
                      uint32_t index, r6_vsl_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_vsl_row_t row;
    uint32_t local;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + vsl_rows_base() +
              (size_t)index * R6_VSL_ROW_SIZE, sizeof(row));
    local = index % R6_VSL_ROWS_PER_FILE;
    if (row.line != 16u + local ||
            row.ident != R6_VSL_ID_MIN + local ||
            vsl_span(data, header, row.value_offset, 1, 1, NULL, 0) != R6_OK ||
            bytes[row.value_offset] < '0' || bytes[row.value_offset] > '2') {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_vsl_parse(const void *data, size_t size, r6_vsl_header_t *out) {
    r6_vsl_header_t header;
    r6_vsl_file_t file;
    r6_vsl_row_t row;
    uint32_t source = 0;
    uint32_t at;
    int result = vsl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = vsl_file_at(data, size, at, &file);
        if (result != R6_OK) {
            return result;
        }
        source += file.size;
    }
    if (source != header.source_bytes) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = vsl_row_at(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_vsl_file(const void *data, size_t size, uint32_t index,
                r6_vsl_file_t *out) {
    return vsl_file_at(data, size, index, out);
}

int r6_vsl_name(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_vsl_header_t header;
    r6_vsl_file_t file;
    int result = vsl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = vsl_file_at(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return vsl_span(data, &header, file.name_offset, file.name_length,
                    0, out, capacity);
}

int r6_vsl_row(const void *data, size_t size, uint32_t index,
               r6_vsl_row_t *out) {
    r6_vsl_header_t header;
    int result = vsl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return vsl_row_at(data, &header, index, out);
}

int r6_vsl_value(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    r6_vsl_header_t header;
    r6_vsl_row_t row;
    int result = vsl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = vsl_row_at(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return vsl_span(data, &header, row.value_offset, 1, 1, out, capacity);
}
