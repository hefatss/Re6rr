/* Bounds-checked reader for the packed sticker/vinyl color inventory. */

#include "r6/r6_sticker_color_catalog.h"

#include "core/internal.h"

enum {
    R6_STC_HEADER_SIZE = 44,
    R6_STC_FILE_SIZE = 20,
    R6_STC_ROW_SIZE = 20,
    R6_STC_FILES = 158,
    R6_STC_ROWS = 1580,
    R6_STC_SIDE = 47,
    R6_STC_VINYL = 111,
    R6_STC_SOURCE = 350159,
    R6_STC_LINES = 9749,
    R6_STC_ROWS_PER_FILE = 10,
    R6_STC_MAX_STRING = 96
};

static const unsigned char stc_magic[8] = {
    'R', '6', 'S', 'T', 'C', 0, 1, 0
};

static size_t stc_files_base(void) {
    return R6_STC_HEADER_SIZE;
}

static size_t stc_rows_base(void) {
    return stc_files_base() + R6_STC_FILES * R6_STC_FILE_SIZE;
}

static size_t stc_strings_base(void) {
    return stc_rows_base() + R6_STC_ROWS * R6_STC_ROW_SIZE;
}

static int stc_header(const void *data, size_t size, r6_stc_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_stc_header_t header;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_STC_HEADER_SIZE ||
            r6_memcmp(bytes, stc_magic, sizeof(stc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_STC_FILES ||
            r6_u32(bytes, 16) != R6_STC_ROWS ||
            r6_u32(bytes, 20) != R6_STC_SIDE ||
            r6_u32(bytes, 24) != R6_STC_VINYL ||
            r6_u32(bytes, 28) != R6_STC_SOURCE ||
            r6_u32(bytes, 32) != R6_STC_LINES || !r6_u32(bytes, 36) ||
            r6_u32(bytes, 40) != 0u ||
            stc_strings_base() + r6_u32(bytes, 36) != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_STC_FILES;
    header.row_count = R6_STC_ROWS;
    header.side_files = R6_STC_SIDE;
    header.vinyl_files = R6_STC_VINYL;
    header.source_bytes = R6_STC_SOURCE;
    header.line_count = R6_STC_LINES;
    header.string_size = r6_u32(bytes, 36);
    header.reserved = 0u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int stc_span(const void *data, const r6_stc_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = stc_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_STC_MAX_STRING || (size_t)offset < base ||
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

static int stc_token_length(const void *data,
                            const r6_stc_header_t *header,
                            uint32_t offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t end = stc_strings_base() + header->string_size;
    uint32_t span = 0;
    if ((size_t)offset < stc_strings_base() || (size_t)offset >= end) {
        return R6_ERR_FORMAT;
    }
    while ((size_t)offset + span < end &&
           bytes[(size_t)offset + span] != 0) {
        span++;
    }
    if ((size_t)offset + span >= end ||
            stc_span(data, header, offset, span, 1, NULL, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    *length = span;
    return R6_OK;
}

static int stc_file_at(const void *data, size_t size, uint32_t index,
                       r6_stc_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_stc_header_t header;
    r6_stc_file_t file;
    char name[R6_STC_MAX_STRING + 1];
    int result;
    if (stc_header(data, size, &header) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + stc_files_base() +
              (size_t)index * R6_STC_FILE_SIZE, sizeof(file));
    result = stc_span(data, &header, file.name_offset, file.name_length,
                      0, name, sizeof(name));
    if (result != R6_OK) {
        return result;
    }
    if (file.kind > 1u || !file.size ||
            file.row_base != index * R6_STC_ROWS_PER_FILE ||
            (file.kind == 0u &&
             (file.name_length < 27u ||
              r6_memcmp(name, "getSideStickerColor_", 20) != 0)) ||
            (file.kind == 1u &&
             (file.name_length < 20u ||
              r6_memcmp(name, "getVinylColor_", 14) != 0)) ||
            r6_memcmp(name + file.name_length - 4, ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int stc_row_at(const void *data, const r6_stc_header_t *header,
                      uint32_t index, r6_stc_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_stc_row_t row;
    uint32_t local = index % R6_STC_ROWS_PER_FILE;
    uint32_t length;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + stc_rows_base() +
              (size_t)index * R6_STC_ROW_SIZE, sizeof(row));
    if (!row.line || row.ident != local ||
            stc_token_length(data, header, row.token0_offset, &length) != R6_OK ||
            stc_token_length(data, header, row.token1_offset, &length) != R6_OK ||
            stc_token_length(data, header, row.token2_offset, &length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_stc_parse(const void *data, size_t size, r6_stc_header_t *out) {
    r6_stc_header_t header;
    r6_stc_file_t file;
    r6_stc_row_t row;
    uint32_t source = 0;
    uint32_t side = 0;
    uint32_t vinyl = 0;
    uint32_t at;
    int result = stc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = stc_file_at(data, size, at, &file);
        if (result != R6_OK) {
            return result;
        }
        source += file.size;
        if (file.kind == 0u) {
            side++;
        } else {
            vinyl++;
        }
    }
    if (source != header.source_bytes || side != header.side_files ||
            vinyl != header.vinyl_files) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = stc_row_at(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_stc_file(const void *data, size_t size, uint32_t index,
                r6_stc_file_t *out) {
    return stc_file_at(data, size, index, out);
}

int r6_stc_name(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_stc_header_t header;
    r6_stc_file_t file;
    int result = stc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = stc_file_at(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return stc_span(data, &header, file.name_offset, file.name_length,
                    0, out, capacity);
}

int r6_stc_row(const void *data, size_t size, uint32_t index,
               r6_stc_row_t *out) {
    r6_stc_header_t header;
    int result = stc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return stc_row_at(data, &header, index, out);
}

int r6_stc_token(const void *data, size_t size, uint32_t index,
                 uint32_t slot, char *out, size_t capacity) {
    r6_stc_header_t header;
    r6_stc_row_t row;
    uint32_t offset;
    uint32_t length;
    int result = stc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = stc_row_at(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot > 2u) {
        return R6_ERR_ARG;
    }
    offset = slot == 0u ? row.token0_offset :
             (slot == 1u ? row.token1_offset : row.token2_offset);
    result = stc_token_length(data, &header, offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return stc_span(data, &header, offset, length, 1, out, capacity);
}
