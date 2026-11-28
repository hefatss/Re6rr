/* Bounds-checked reader for packed MA61 color block inventories. */

#include "r6/r6_color_block_catalog.h"

#include "core/internal.h"

enum {
    R6_CLR_HEADER_SIZE = 52,
    R6_CLR_FILE_SIZE = 24,
    R6_CLR_ROW_SIZE = 16,
    R6_CLR_FILES = 2,
    R6_CLR_ROWS = 45,
    R6_CLR_LINES = 1194,
    R6_CLR_SOURCE = 40196,
    R6_CLR_TOKENS = 19,
    R6_CLR_VEC4 = 3,
    R6_CLR_FLOATS = 4,
    R6_CLR_INTS = 3,
    R6_CLR_MAX_STRING = 96
};

static const unsigned char clr_magic[8] = {
    'R', '6', 'C', 'L', 'R', 0, 1, 0
};

static const uint32_t clr_sizes[2] = {8065u, 32131u};
static const uint32_t clr_lines[2] = {247u, 947u};
static const uint32_t clr_first[2] = {29u, 64u};
static const uint32_t clr_bases[2] = {0u, 5u};
static const uint32_t clr_blocks[2] = {5u, 40u};

static int clr_header(const void *data, size_t size,
                      r6_color_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_color_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_CLR_HEADER_SIZE ||
            r6_memcmp(bytes, clr_magic, sizeof(clr_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_CLR_FILES ||
            r6_u32(bytes, 16) != R6_CLR_ROWS ||
            r6_u32(bytes, 20) != R6_CLR_LINES || !r6_u32(bytes, 24) ||
            r6_u32(bytes, 28) != R6_CLR_SOURCE ||
            r6_u32(bytes, 32) != R6_CLR_TOKENS ||
            r6_u32(bytes, 36) != R6_CLR_VEC4 ||
            r6_u32(bytes, 40) != R6_CLR_FLOATS ||
            r6_u32(bytes, 44) != R6_CLR_INTS ||
            r6_u32(bytes, 48) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_CLR_FILES;
    header.row_count = R6_CLR_ROWS;
    header.line_count = R6_CLR_LINES;
    header.string_size = r6_u32(bytes, 24);
    header.source_bytes = R6_CLR_SOURCE;
    header.token_count = R6_CLR_TOKENS;
    header.vec4_max = R6_CLR_VEC4;
    header.float_max = R6_CLR_FLOATS;
    header.int_max = R6_CLR_INTS;
    header.reserved = 0u;
    base = R6_CLR_HEADER_SIZE +
           (size_t)header.file_count * R6_CLR_FILE_SIZE +
           (size_t)header.row_count * R6_CLR_ROW_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t clr_rows_base(void) {
    return R6_CLR_HEADER_SIZE + R6_CLR_FILES * R6_CLR_FILE_SIZE;
}

static size_t clr_strings_base(void) {
    return clr_rows_base() + R6_CLR_ROWS * R6_CLR_ROW_SIZE;
}

static int clr_string(const void *data,
                      const r6_color_header_t *header,
                      uint32_t offset, uint32_t length, int digits) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = clr_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (length > R6_CLR_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0 ||
            (!digits && !length)) {
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
    return R6_OK;
}

static int clr_copy(const void *data,
                    const r6_color_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = clr_string(data, header, offset, length, 0);
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

static int clr_file(const void *data, size_t size, uint32_t index,
                    r6_color_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_color_header_t header;
    r6_color_file_t file;
    int result = clr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + R6_CLR_HEADER_SIZE +
              (size_t)index * R6_CLR_FILE_SIZE, sizeof(file));
    if (file.size != clr_sizes[index] || file.lines != clr_lines[index] ||
            file.first_line != clr_first[index] ||
            file.row_base != clr_bases[index] || file.path_length < 5 ||
            clr_string(data, &header, file.path_offset,
                       file.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int clr_token_span(const void *data,
                          const r6_color_header_t *header,
                          uint32_t index, uint32_t slot,
                          uint32_t *offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_color_row_t row;
    uint32_t at;
    uint32_t cursor;
    uint32_t span;
    size_t end = clr_strings_base() + header->string_size;
    if (index >= header->row_count || slot >= header->token_count) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + clr_rows_base() +
              (size_t)index * R6_CLR_ROW_SIZE, sizeof(row));
    cursor = row.token_offset;
    for (at = 0; at <= slot; at++) {
        if ((size_t)cursor >= end) {
            return R6_ERR_FORMAT;
        }
        span = 0;
        while ((size_t)cursor + span < end &&
               bytes[(size_t)cursor + span] != 0) {
            span++;
        }
        if ((size_t)cursor + span >= end ||
                clr_string(data, header, cursor, span, 1) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        if (at == slot) {
            *offset = cursor;
            *length = span;
            return R6_OK;
        }
        cursor += span + 1u;
    }
    return R6_ERR_FORMAT;
}

static int clr_row(const void *data,
                   const r6_color_header_t *header,
                   uint32_t index, r6_color_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_color_row_t row;
    uint32_t offset;
    uint32_t length;
    uint32_t slot;
    uint32_t expected;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + clr_rows_base() +
              (size_t)index * R6_CLR_ROW_SIZE, sizeof(row));
    if (clr_string(data, header, row.name_offset, row.name_length, 0) != R6_OK ||
            row.name_length < 5 ||
            r6_memcmp(bytes + row.name_offset, "type", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    expected = index < clr_bases[1] ? 0u : 1u;
    if (row.line != clr_first[expected] +
            (index - clr_bases[expected]) * 19u) {
        return R6_ERR_FORMAT;
    }
    for (slot = 0; slot < header->token_count; slot++) {
        if (clr_token_span(data, header, index, slot,
                           &offset, &length) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_color_parse(const void *data, size_t size, r6_color_header_t *out) {
    r6_color_header_t header;
    r6_color_file_t file;
    r6_color_row_t row;
    char text[R6_CLR_MAX_STRING + 1];
    uint32_t source = 0;
    uint32_t rows = 0;
    uint32_t lines = 0;
    uint32_t at;
    int result = clr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = clr_file(data, size, at, &file);
        if (result != R6_OK || file.row_base != rows) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        lines += file.lines;
        rows += clr_blocks[at];
    }
    if (source != header.source_bytes || lines != header.line_count ||
            rows != header.row_count ||
            clr_file(data, size, 0, &file) != R6_OK ||
            clr_copy(data, &header, file.path_offset, file.path_length,
                     text, sizeof(text)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = clr_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_color_file(const void *data, size_t size, uint32_t index,
                  r6_color_file_t *out) {
    return clr_file(data, size, index, out);
}

int r6_color_path(const void *data, size_t size, uint32_t index,
                  char *out, size_t capacity) {
    r6_color_header_t header;
    r6_color_file_t file;
    int result = clr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = clr_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return clr_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_color_row(const void *data, size_t size, uint32_t index,
                 r6_color_row_t *out) {
    r6_color_header_t header;
    int result = clr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return clr_row(data, &header, index, out);
}

int r6_color_name(const void *data, size_t size, uint32_t index,
                  char *out, size_t capacity) {
    r6_color_header_t header;
    r6_color_row_t row;
    int result = clr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = clr_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return clr_copy(data, &header, row.name_offset, row.name_length,
                    out, capacity);
}

int r6_color_token(const void *data, size_t size, uint32_t index,
                   uint32_t slot, char *out, size_t capacity) {
    r6_color_header_t header;
    uint32_t offset;
    uint32_t length;
    int result = clr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = clr_token_span(data, &header, index, slot, &offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return clr_copy(data, &header, offset, length, out, capacity);
}
