/* Bounds-checked reader for the packed playerCar color block inventory. */

#include "r6/r6_player_color_catalog.h"

#include "core/internal.h"

enum {
    R6_PCC_HEADER_SIZE = 40,
    R6_PCC_FILE_SIZE = 28,
    R6_PCC_ROW_SIZE = 16,
    R6_PCC_FILES = 300,
    R6_PCC_ROWS = 6133,
    R6_PCC_TOKENS = 116527,
    R6_PCC_LINES = 166760,
    R6_PCC_SOURCE = 5585086,
    R6_PCC_TOKENS_PER_ROW = 19,
    R6_PCC_BLOCK_LINES = 19,
    R6_PCC_MAX_STRING = 96
};

static const unsigned char pcc_magic[8] = {
    'R', '6', 'P', 'C', 'C', 0, 1, 0
};

static size_t pcc_files_base(void) {
    return R6_PCC_HEADER_SIZE;
}

static size_t pcc_rows_base(void) {
    return pcc_files_base() + R6_PCC_FILES * R6_PCC_FILE_SIZE;
}

static size_t pcc_strings_base(void) {
    return pcc_rows_base() + R6_PCC_ROWS * R6_PCC_ROW_SIZE;
}

static int pcc_header(const void *data, size_t size, r6_pcc_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pcc_header_t header;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_PCC_HEADER_SIZE ||
            r6_memcmp(bytes, pcc_magic, sizeof(pcc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_PCC_FILES ||
            r6_u32(bytes, 16) != R6_PCC_ROWS ||
            r6_u32(bytes, 20) != R6_PCC_TOKENS ||
            r6_u32(bytes, 24) != R6_PCC_LINES ||
            r6_u32(bytes, 28) != R6_PCC_SOURCE || !r6_u32(bytes, 32) ||
            r6_u32(bytes, 36) != 0u ||
            pcc_strings_base() + r6_u32(bytes, 32) != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_PCC_FILES;
    header.row_count = R6_PCC_ROWS;
    header.token_count = R6_PCC_TOKENS;
    header.line_count = R6_PCC_LINES;
    header.source_bytes = R6_PCC_SOURCE;
    header.string_size = r6_u32(bytes, 32);
    header.reserved = 0u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int pcc_span(const void *data, const r6_pcc_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = pcc_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_PCC_MAX_STRING || (size_t)offset < base ||
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

static int pcc_token_length(const void *data,
                            const r6_pcc_header_t *header,
                            uint32_t offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t end = pcc_strings_base() + header->string_size;
    uint32_t span = 0;
    if ((size_t)offset < pcc_strings_base() || (size_t)offset >= end) {
        return R6_ERR_FORMAT;
    }
    while ((size_t)offset + span < end &&
           bytes[(size_t)offset + span] != 0) {
        span++;
    }
    if ((size_t)offset + span >= end ||
            pcc_span(data, header, offset, span, 1, NULL, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    *length = span;
    return R6_OK;
}

static int pcc_file_at(const void *data, size_t size, uint32_t index,
                       r6_pcc_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pcc_header_t header;
    r6_pcc_file_t file;
    char name[R6_PCC_MAX_STRING + 1];
    int result;
    if (pcc_header(data, size, &header) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + pcc_files_base() +
              (size_t)index * R6_PCC_FILE_SIZE, sizeof(file));
    result = pcc_span(data, &header, file.name_offset, file.name_length,
                      0, name, sizeof(name));
    if (result != R6_OK) {
        return result;
    }
    if (file.name_length < 22u || !file.size || !file.lines ||
            !file.start_line || !file.color_max || file.color_max > 40u ||
            file.row_base >= header.row_count ||
            (r6_memcmp(name + file.name_length - 16,
                       "DefaultColor.lua", 16) != 0 &&
             r6_memcmp(name + file.name_length - 15,
                       "CustomColor.lua", 15) != 0)) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static uint32_t pcc_type_name(uint32_t local, char *out) {
    uint32_t value = local;
    uint32_t digits = 1;
    uint32_t at;
    while (value >= 10u) {
        value /= 10u;
        digits++;
    }
    r6_memcpy(out, "type", 4);
    value = local;
    for (at = 0; at < digits; at++) {
        out[4u + digits - 1u - at] = (char)('0' + value % 10u);
        value /= 10u;
    }
    out[4u + digits] = 0;
    return 4u + digits;
}

static int pcc_row_at(const void *data, const r6_pcc_header_t *header,
                      const r6_pcc_file_t *file, uint32_t local,
                      r6_pcc_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pcc_row_t row;
    uint32_t length;
    uint32_t slot;
    uint32_t offset;
    uint32_t expected_length;
    char name[R6_PCC_MAX_STRING + 1];
    char expected[16];
    int result;
    if (local >= file->color_max || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + pcc_rows_base() +
              (size_t)(file->row_base + local) * R6_PCC_ROW_SIZE,
              sizeof(row));
    result = pcc_span(data, header, row.name_offset, row.name_length,
                      0, name, sizeof(name));
    expected_length = pcc_type_name(local, expected);
    if (result != R6_OK || row.name_length != expected_length ||
            r6_memcmp(name, expected, expected_length) != 0 ||
            row.line != file->start_line + 1u +
                        local * R6_PCC_BLOCK_LINES) {
        return result != R6_OK ? result : R6_ERR_FORMAT;
    }
    offset = row.token_offset;
    for (slot = 0; slot < R6_PCC_TOKENS_PER_ROW; slot++) {
        result = pcc_token_length(data, header, offset, &length);
        if (result != R6_OK) {
            return result;
        }
        offset += length + 1u;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int pcc_owner(const void *data, size_t size, uint32_t index,
                     r6_pcc_file_t *out) {
    r6_pcc_header_t header;
    r6_pcc_file_t file;
    uint32_t low = 0;
    uint32_t high = R6_PCC_FILES;
    if (pcc_header(data, size, &header) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (index >= header.row_count || !out) {
        return R6_ERR_ARG;
    }
    while (low < high) {
        uint32_t mid = low + (high - low) / 2u;
        if (pcc_file_at(data, size, mid, &file) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        if (file.row_base <= index) {
            low = mid + 1u;
        } else {
            high = mid;
        }
    }
    if (!low || pcc_file_at(data, size, low - 1u, &file) != R6_OK ||
            index - file.row_base >= file.color_max) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

int r6_pcc_parse(const void *data, size_t size, r6_pcc_header_t *out) {
    r6_pcc_header_t header;
    r6_pcc_file_t file;
    r6_pcc_row_t row;
    uint32_t source = 0;
    uint32_t lines = 0;
    uint32_t rows = 0;
    uint32_t at;
    uint32_t local;
    int result = pcc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = pcc_file_at(data, size, at, &file);
        if (result != R6_OK || file.row_base != rows) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        lines += file.lines;
        rows += file.color_max;
        for (local = 0; local < file.color_max; local++) {
            result = pcc_row_at(data, &header, &file, local, &row);
            if (result != R6_OK) {
                return result;
            }
        }
    }
    if (source != header.source_bytes || lines != header.line_count ||
            rows != header.row_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_pcc_file(const void *data, size_t size, uint32_t index,
                r6_pcc_file_t *out) {
    return pcc_file_at(data, size, index, out);
}

int r6_pcc_name(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_pcc_header_t header;
    r6_pcc_file_t file;
    int result = pcc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = pcc_file_at(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return pcc_span(data, &header, file.name_offset, file.name_length,
                    0, out, capacity);
}

int r6_pcc_row(const void *data, size_t size, uint32_t index,
               r6_pcc_row_t *out) {
    r6_pcc_header_t header;
    r6_pcc_file_t file;
    int result = pcc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = pcc_owner(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return pcc_row_at(data, &header, &file, index - file.row_base, out);
}

int r6_pcc_token(const void *data, size_t size, uint32_t index,
                 uint32_t slot, char *out, size_t capacity) {
    r6_pcc_header_t header;
    r6_pcc_file_t file;
    r6_pcc_row_t row;
    uint32_t offset;
    uint32_t length;
    uint32_t at;
    int result = pcc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = pcc_owner(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    result = pcc_row_at(data, &header, &file, index - file.row_base, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot >= R6_PCC_TOKENS_PER_ROW) {
        return R6_ERR_ARG;
    }
    offset = row.token_offset;
    for (at = 0; at < slot; at++) {
        result = pcc_token_length(data, &header, offset, &length);
        if (result != R6_OK) {
            return result;
        }
        offset += length + 1u;
    }
    result = pcc_token_length(data, &header, offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return pcc_span(data, &header, offset, length, 1, out, capacity);
}
