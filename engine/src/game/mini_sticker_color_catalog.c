/* Bounds-checked reader for the packed mini-sticker color inventory. */

#include "r6/r6_mini_sticker_color_catalog.h"

#include "core/internal.h"

enum {
    R6_MSC_HEADER_SIZE = 44,
    R6_MSC_FILE_SIZE = 16,
    R6_MSC_ROW_SIZE = 20,
    R6_MSC_FILES = 417,
    R6_MSC_ROWS = 8340,
    R6_MSC_TOKENS = 25020,
    R6_MSC_LINES = 61,
    R6_MSC_VINYL = 10,
    R6_MSC_SOURCE = 986467,
    R6_MSC_MAX_STRING = 96
};

static const unsigned char msc_magic[8] = {
    'R', '6', 'M', 'S', 'C', 0, 1, 0
};

static size_t msc_files_base(void) {
    return R6_MSC_HEADER_SIZE;
}

static size_t msc_rows_base(void) {
    return msc_files_base() + R6_MSC_FILES * R6_MSC_FILE_SIZE;
}

static size_t msc_strings_base(void) {
    return msc_rows_base() + R6_MSC_ROWS * R6_MSC_ROW_SIZE;
}

static int msc_header(const void *data, size_t size, r6_msc_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msc_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_MSC_HEADER_SIZE ||
            r6_memcmp(bytes, msc_magic, sizeof(msc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_MSC_FILES ||
            r6_u32(bytes, 16) != R6_MSC_ROWS ||
            r6_u32(bytes, 20) != R6_MSC_TOKENS ||
            r6_u32(bytes, 24) != R6_MSC_LINES ||
            r6_u32(bytes, 28) != R6_MSC_VINYL ||
            r6_u32(bytes, 32) != R6_MSC_SOURCE || !r6_u32(bytes, 36) ||
            r6_u32(bytes, 40) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_MSC_FILES;
    header.row_count = R6_MSC_ROWS;
    header.token_count = R6_MSC_TOKENS;
    header.line_count = R6_MSC_LINES;
    header.vinyl_max = R6_MSC_VINYL;
    header.source_bytes = R6_MSC_SOURCE;
    header.string_size = r6_u32(bytes, 36);
    header.reserved = 0u;
    base = msc_strings_base() + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int msc_span(const void *data, const r6_msc_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = msc_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_MSC_MAX_STRING || (size_t)offset < base ||
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

static int msc_token_length(const void *data,
                            const r6_msc_header_t *header,
                            uint32_t offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t end = msc_strings_base() + header->string_size;
    uint32_t span = 0;
    if ((size_t)offset >= end) {
        return R6_ERR_FORMAT;
    }
    while ((size_t)offset + span < end &&
           bytes[(size_t)offset + span] != 0) {
        span++;
    }
    if ((size_t)offset + span >= end ||
            msc_span(data, header, offset, span, 1, NULL, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    *length = span;
    return R6_OK;
}

static int msc_file(const void *data, size_t size, uint32_t index,
                    r6_msc_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msc_header_t header;
    r6_msc_file_t file;
    char name[R6_MSC_MAX_STRING + 1];
    int result = msc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + msc_files_base() +
              (size_t)index * R6_MSC_FILE_SIZE, sizeof(file));
    result = msc_span(data, &header, file.name_offset, file.name_length,
                      0, name, sizeof(name));
    if (result != R6_OK || file.name_length < 27 ||
            r6_memcmp(name + file.name_length - 4, ".lua", 4) != 0 ||
            r6_memcmp(name, "getMiniStickerColor_", 20) != 0 ||
            !file.size || file.row_base != index * 20u) {
        return result != R6_OK ? result : R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int msc_row(const void *data, const r6_msc_header_t *header,
                   uint32_t index, r6_msc_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msc_row_t row;
    uint32_t slot;
    uint32_t offsets[3];
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + msc_rows_base() +
              (size_t)index * R6_MSC_ROW_SIZE, sizeof(row));
    slot = index % 20u;
    if (row.line != 17u + slot + (slot >= 10u ? 1u : 0u) ||
            row.slot != slot % 10u) {
        return R6_ERR_FORMAT;
    }
    offsets[0] = row.token0_offset;
    offsets[1] = row.token1_offset;
    offsets[2] = row.token2_offset;
    for (slot = 0; slot < 3u; slot++) {
        uint32_t length;
        if (msc_token_length(data, header, offsets[slot],
                             &length) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_msc_parse(const void *data, size_t size, r6_msc_header_t *out) {
    r6_msc_header_t header;
    r6_msc_file_t file;
    r6_msc_row_t row;
    uint32_t source = 0;
    uint32_t rows = 0;
    uint32_t at;
    int result = msc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = msc_file(data, size, at, &file);
        if (result != R6_OK || file.row_base != rows) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        rows += 20u;
    }
    if (source != header.source_bytes || rows != header.row_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = msc_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_msc_file(const void *data, size_t size, uint32_t index,
                r6_msc_file_t *out) {
    return msc_file(data, size, index, out);
}

int r6_msc_name(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_msc_header_t header;
    r6_msc_file_t file;
    int result = msc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = msc_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return msc_span(data, &header, file.name_offset, file.name_length,
                    0, out, capacity);
}

int r6_msc_row(const void *data, size_t size, uint32_t index,
               r6_msc_row_t *out) {
    r6_msc_header_t header;
    int result = msc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return msc_row(data, &header, index, out);
}

int r6_msc_token(const void *data, size_t size, uint32_t index,
                 uint32_t slot, char *out, size_t capacity) {
    r6_msc_header_t header;
    r6_msc_row_t row;
    uint32_t offset;
    uint32_t length;
    int result = msc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = msc_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot > 2u) {
        return R6_ERR_ARG;
    }
    offset = slot == 0u ? row.token0_offset :
             (slot == 1u ? row.token1_offset : row.token2_offset);
    result = msc_token_length(data, &header, offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return msc_span(data, &header, offset, length, 1, out, capacity);
}
