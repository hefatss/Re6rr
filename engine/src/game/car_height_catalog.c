/* Bounds-checked reader for the packed car height and aero row inventory. */

#include "r6/r6_car_height_catalog.h"

#include "core/internal.h"

enum {
    R6_CHG_HEADER_SIZE = 48,
    R6_CHG_FILE_SIZE = 16,
    R6_CHG_ROW_SIZE = 20,
    R6_CHG_FILES = 149,
    R6_CHG_ROWS = 2384,
    R6_CHG_TOKENS = 4172,
    R6_CHG_LINES = 231,
    R6_CHG_HEIGHT = 4,
    R6_CHG_AERO = 12,
    R6_CHG_SOURCE = 1575214,
    R6_CHG_MAX_STRING = 96
};

static const unsigned char chg_magic[8] = {
    'R', '6', 'C', 'H', 'G', 0, 1, 0
};

static const char chg_labels[12] = "NABCDEFGHIJK";

static size_t chg_files_base(void) {
    return R6_CHG_HEADER_SIZE;
}

static size_t chg_rows_base(void) {
    return chg_files_base() + R6_CHG_FILES * R6_CHG_FILE_SIZE;
}

static size_t chg_strings_base(void) {
    return chg_rows_base() + R6_CHG_ROWS * R6_CHG_ROW_SIZE;
}

static int chg_header(const void *data, size_t size, r6_chg_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_chg_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_CHG_HEADER_SIZE ||
            r6_memcmp(bytes, chg_magic, sizeof(chg_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_CHG_FILES ||
            r6_u32(bytes, 16) != R6_CHG_ROWS ||
            r6_u32(bytes, 20) != R6_CHG_TOKENS ||
            r6_u32(bytes, 24) != R6_CHG_LINES ||
            r6_u32(bytes, 28) != R6_CHG_HEIGHT ||
            r6_u32(bytes, 32) != R6_CHG_AERO ||
            r6_u32(bytes, 36) != R6_CHG_SOURCE || !r6_u32(bytes, 40) ||
            r6_u32(bytes, 44) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_CHG_FILES;
    header.row_count = R6_CHG_ROWS;
    header.token_count = R6_CHG_TOKENS;
    header.line_count = R6_CHG_LINES;
    header.height_rows = R6_CHG_HEIGHT;
    header.aero_rows = R6_CHG_AERO;
    header.source_bytes = R6_CHG_SOURCE;
    header.string_size = r6_u32(bytes, 40);
    header.reserved = 0u;
    base = chg_strings_base() + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int chg_span(const void *data, const r6_chg_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = chg_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_CHG_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (digits) {
            if ((value < '0' || value > '9') && value != '.' &&
                    (at != 0u || value != '-')) {
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

static int chg_token_length(const void *data,
                            const r6_chg_header_t *header,
                            uint32_t offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t end = chg_strings_base() + header->string_size;
    uint32_t span = 0;
    if ((size_t)offset >= end) {
        return R6_ERR_FORMAT;
    }
    while ((size_t)offset + span < end &&
           bytes[(size_t)offset + span] != 0) {
        span++;
    }
    if ((size_t)offset + span >= end ||
            chg_span(data, header, offset, span, 1, NULL, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    *length = span;
    return R6_OK;
}

static int chg_file(const void *data, size_t size, uint32_t index,
                    r6_chg_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_chg_header_t header;
    r6_chg_file_t file;
    char name[R6_CHG_MAX_STRING + 1];
    int result = chg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + chg_files_base() +
              (size_t)index * R6_CHG_FILE_SIZE, sizeof(file));
    result = chg_span(data, &header, file.name_offset, file.name_length,
                      0, name, sizeof(name));
    if (result != R6_OK || file.name_length < 18 ||
            r6_memcmp(name, "CarHightDown_", 13) != 0 ||
            r6_memcmp(name + file.name_length - 4, ".lua", 4) != 0 ||
            !file.size || file.row_base != index * 16u) {
        return result != R6_OK ? result : R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int chg_row(const void *data, const r6_chg_header_t *header,
                   uint32_t index, r6_chg_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_chg_row_t row;
    uint32_t local;
    uint32_t length;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + chg_rows_base() +
              (size_t)index * R6_CHG_ROW_SIZE, sizeof(row));
    local = index % 16u;
    if (local < R6_CHG_HEIGHT) {
        if (row.line != 12u + local || row.token1_offset ||
                row.label_offset || row.label_length ||
                chg_token_length(data, header, row.token0_offset,
                                 &length) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    } else {
        if (row.line != 44u + local - R6_CHG_HEIGHT ||
                !row.token1_offset || row.label_length != 1u ||
                chg_span(data, header, row.label_offset, 1u, 0,
                         NULL, 0) != R6_OK ||
                bytes[row.label_offset] !=
                    (unsigned char)chg_labels[local - R6_CHG_HEIGHT] ||
                chg_token_length(data, header, row.token0_offset,
                                 &length) != R6_OK ||
                chg_token_length(data, header, row.token1_offset,
                                 &length) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_chg_parse(const void *data, size_t size, r6_chg_header_t *out) {
    r6_chg_header_t header;
    r6_chg_file_t file;
    r6_chg_row_t row;
    uint32_t source = 0;
    uint32_t rows = 0;
    uint32_t at;
    int result = chg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = chg_file(data, size, at, &file);
        if (result != R6_OK || file.row_base != rows) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        rows += 16u;
    }
    if (source != header.source_bytes || rows != header.row_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = chg_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_chg_file(const void *data, size_t size, uint32_t index,
                r6_chg_file_t *out) {
    return chg_file(data, size, index, out);
}

int r6_chg_name(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_chg_header_t header;
    r6_chg_file_t file;
    int result = chg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = chg_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return chg_span(data, &header, file.name_offset, file.name_length,
                    0, out, capacity);
}

int r6_chg_row(const void *data, size_t size, uint32_t index,
               r6_chg_row_t *out) {
    r6_chg_header_t header;
    int result = chg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return chg_row(data, &header, index, out);
}

int r6_chg_token(const void *data, size_t size, uint32_t index,
                 uint32_t slot, char *out, size_t capacity) {
    r6_chg_header_t header;
    r6_chg_row_t row;
    uint32_t offset;
    uint32_t length;
    int result = chg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = chg_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot > 1u || (slot == 1u && !row.token1_offset)) {
        return R6_ERR_ARG;
    }
    offset = slot == 0u ? row.token0_offset : row.token1_offset;
    result = chg_token_length(data, &header, offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return chg_span(data, &header, offset, length, 1, out, capacity);
}

int r6_chg_label(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    r6_chg_header_t header;
    r6_chg_row_t row;
    int result = chg_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = chg_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!row.label_length) {
        return R6_ERR_ARG;
    }
    return chg_span(data, &header, row.label_offset, row.label_length,
                    0, out, capacity);
}
