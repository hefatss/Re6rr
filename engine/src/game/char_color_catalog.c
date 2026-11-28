/* Bounds-checked reader for the packed charCar color block inventory. */

#include "r6/r6_char_color_catalog.h"

#include "core/internal.h"

enum {
    R6_CCC_HEADER_SIZE = 52,
    R6_CCC_FILE_SIZE = 32,
    R6_CCC_ROW_SIZE = 16,
    R6_CCC_FILES = 100,
    R6_CCC_ROWS = 122,
    R6_CCC_TOKENS = 2318,
    R6_CCC_LINES = 17137,
    R6_CCC_SOURCE = 535375,
    R6_CCC_TOKENS_PER_ROW = 19,
    R6_CCC_MAX_STRING = 96
};

static const unsigned char ccc_magic[8] = {
    'R', '6', 'C', 'C', 'C', 0, 1, 0
};

static size_t ccc_files_base(void) {
    return R6_CCC_HEADER_SIZE;
}

static size_t ccc_rows_base(void) {
    return ccc_files_base() + R6_CCC_FILES * R6_CCC_FILE_SIZE;
}

static size_t ccc_strings_base(void) {
    return ccc_rows_base() + R6_CCC_ROWS * R6_CCC_ROW_SIZE;
}

static int ccc_header(const void *data, size_t size, r6_ccc_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ccc_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_CCC_HEADER_SIZE ||
            r6_memcmp(bytes, ccc_magic, sizeof(ccc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_CCC_FILES ||
            r6_u32(bytes, 16) != R6_CCC_ROWS ||
            r6_u32(bytes, 20) != R6_CCC_TOKENS ||
            r6_u32(bytes, 24) != R6_CCC_LINES ||
            r6_u32(bytes, 28) != R6_CCC_SOURCE || !r6_u32(bytes, 32) ||
            r6_u32(bytes, 36) != 95u || r6_u32(bytes, 40) != 4u ||
            r6_u32(bytes, 44) != 1u || r6_u32(bytes, 48) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_CCC_FILES;
    header.row_count = R6_CCC_ROWS;
    header.token_count = R6_CCC_TOKENS;
    header.line_count = R6_CCC_LINES;
    header.source_bytes = R6_CCC_SOURCE;
    header.string_size = r6_u32(bytes, 32);
    header.max_one = 95u;
    header.max_six = 4u;
    header.max_three = 1u;
    header.reserved = 0u;
    base = ccc_strings_base() + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int ccc_span(const void *data, const r6_ccc_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = ccc_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_CCC_MAX_STRING || (size_t)offset < base ||
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

static int ccc_token_length(const void *data,
                            const r6_ccc_header_t *header,
                            uint32_t offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t end = ccc_strings_base() + header->string_size;
    uint32_t span = 0;
    if ((size_t)offset >= end) {
        return R6_ERR_FORMAT;
    }
    while ((size_t)offset + span < end &&
           bytes[(size_t)offset + span] != 0) {
        span++;
    }
    if ((size_t)offset + span >= end ||
            ccc_span(data, header, offset, span, 1, NULL, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    *length = span;
    return R6_OK;
}

static int ccc_file(const void *data, size_t size, uint32_t index,
                    r6_ccc_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ccc_header_t header;
    r6_ccc_file_t file;
    char name[R6_CCC_MAX_STRING + 1];
    int result = ccc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + ccc_files_base() +
              (size_t)index * R6_CCC_FILE_SIZE, sizeof(file));
    result = ccc_span(data, &header, file.name_offset, file.name_length,
                      0, name, sizeof(name));
    if (result != R6_OK || file.name_length < 22 ||
            r6_memcmp(name, "CRC_", 4) != 0 ||
            r6_memcmp(name + file.name_length - 17,
                      "_DefaultColor.lua", 17) != 0 ||
            !file.size || !file.lines || !file.start_line ||
            (file.color_max != 1u && file.color_max != 3u &&
             file.color_max != 6u) ||
            (file.block_lines != 18u && file.block_lines != 19u)) {
        return result != R6_OK ? result : R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int ccc_row(const void *data, size_t size,
                   const r6_ccc_header_t *header,
                   uint32_t index, r6_ccc_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ccc_file_t file;
    r6_ccc_row_t row;
    uint32_t at;
    uint32_t found = 0;
    uint32_t local = 0;
    uint32_t slot;
    uint32_t length;
    char name[R6_CCC_MAX_STRING + 1];
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header->file_count; at++) {
        if (ccc_file(data, size, at, &file) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        if (index >= file.row_base && index - file.row_base < file.color_max) {
            local = index - file.row_base;
            found = 1u;
            break;
        }
    }
    if (!found) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(&row, bytes + ccc_rows_base() +
              (size_t)index * R6_CCC_ROW_SIZE, sizeof(row));
    if (ccc_span(data, header, row.name_offset, row.name_length, 0,
                 name, sizeof(name)) != R6_OK ||
            row.name_length != 5u ||
            r6_memcmp(name, "type", 4) != 0 ||
            name[4] != (char)('0' + local) ||
            row.line != file.start_line + 1u + local * file.block_lines) {
        return R6_ERR_FORMAT;
    }
    for (slot = 0; slot < R6_CCC_TOKENS_PER_ROW; slot++) {
        uint32_t offset = row.token_offset;
        uint32_t cursor = 0;
        while (cursor < slot) {
            if (ccc_token_length(data, header, offset, &length) != R6_OK) {
                return R6_ERR_FORMAT;
            }
            offset += length + 1u;
            cursor++;
        }
        if (ccc_token_length(data, header, offset, &length) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_ccc_parse(const void *data, size_t size, r6_ccc_header_t *out) {
    r6_ccc_header_t header;
    r6_ccc_file_t file;
    r6_ccc_row_t row;
    uint32_t source = 0;
    uint32_t lines = 0;
    uint32_t rows = 0;
    uint32_t max_one = 0;
    uint32_t max_six = 0;
    uint32_t max_three = 0;
    uint32_t at;
    int result = ccc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = ccc_file(data, size, at, &file);
        if (result != R6_OK || file.row_base != rows) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        lines += file.lines;
        rows += file.color_max;
        if (file.color_max == 1u) {
            max_one++;
        } else if (file.color_max == 6u) {
            max_six++;
        } else {
            max_three++;
        }
    }
    if (source != header.source_bytes || lines != header.line_count ||
            rows != header.row_count || max_one != header.max_one ||
            max_six != header.max_six || max_three != header.max_three) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = ccc_row(data, size, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_ccc_file(const void *data, size_t size, uint32_t index,
                r6_ccc_file_t *out) {
    return ccc_file(data, size, index, out);
}

int r6_ccc_name(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_ccc_header_t header;
    r6_ccc_row_t row;
    int result = ccc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ccc_row(data, size, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ccc_span(data, &header, row.name_offset, row.name_length,
                    0, out, capacity);
}

int r6_ccc_row(const void *data, size_t size, uint32_t index,
               r6_ccc_row_t *out) {
    r6_ccc_header_t header;
    int result = ccc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return ccc_row(data, size, &header, index, out);
}

int r6_ccc_token(const void *data, size_t size, uint32_t index,
                 uint32_t slot, char *out, size_t capacity) {
    r6_ccc_header_t header;
    r6_ccc_row_t row;
    uint32_t offset;
    uint32_t length;
    uint32_t at;
    int result = ccc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ccc_row(data, size, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot >= R6_CCC_TOKENS_PER_ROW) {
        return R6_ERR_ARG;
    }
    offset = row.token_offset;
    for (at = 0; at < slot; at++) {
        if (ccc_token_length(data, &header, offset, &length) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        offset += length + 1u;
    }
    result = ccc_token_length(data, &header, offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return ccc_span(data, &header, offset, length, 1, out, capacity);
}
