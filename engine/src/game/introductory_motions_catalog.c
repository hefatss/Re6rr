/* Bounds-checked reader for packed introductory-motion facts. */

#include "r6/r6_introductory_motions_catalog.h"

#include "core/internal.h"

enum {
    R6_INT_HEADER_SIZE = 36,
    R6_INT_ROW_SIZE = 20,
    R6_INT_FUNCTION_SIZE = 8,
    R6_INT_ROWS = 2,
    R6_INT_NAMES = 4,
    R6_INT_FUNCTIONS = 6
};

static const unsigned char int_magic[8] = {
    'R', '6', 'I', 'N', 'T', 0, 1, 0
};

static int int_header(const void *data, size_t size,
                      r6_introductory_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_introductory_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_INT_HEADER_SIZE ||
            r6_memcmp(bytes, int_magic, sizeof(int_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_INT_ROWS ||
            r6_u32(bytes, 16) != R6_INT_NAMES ||
            r6_u32(bytes, 20) != R6_INT_FUNCTIONS || !r6_u32(bytes, 24) ||
            r6_u32(bytes, 28) || r6_u32(bytes, 32)) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.row_count = r6_u32(bytes, 12);
    header.name_count = r6_u32(bytes, 16);
    header.function_count = r6_u32(bytes, 20);
    header.string_size = r6_u32(bytes, 24);
    header.start_frame = 0u;
    header.blank_frame = 0u;
    base = R6_INT_HEADER_SIZE +
           (size_t)header.row_count * R6_INT_ROW_SIZE +
           (size_t)header.function_count * R6_INT_FUNCTION_SIZE;
    if (base > (size_t)-1 - header.string_size ||
            base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t int_strings_base(void) {
    return R6_INT_HEADER_SIZE + R6_INT_ROWS * R6_INT_ROW_SIZE +
           R6_INT_FUNCTIONS * R6_INT_FUNCTION_SIZE;
}

static int int_string(const void *data, const r6_introductory_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = int_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > 64 || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        if (bytes[(size_t)offset + at] >= 0x80u) {
            return R6_ERR_FORMAT;
        }
    }
    if (bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int int_row(const void *data, size_t size, uint32_t index,
                   r6_introductory_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_introductory_header_t header;
    r6_introductory_row_t row;
    size_t at;
    int result = int_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.row_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_INT_HEADER_SIZE + (size_t)index * R6_INT_ROW_SIZE;
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.wait != (index == 0u ? 20u : 60u) || !row.left_length ||
            !row.right_length ||
            int_string(data, &header, row.left_offset,
                       row.left_length) != R6_OK ||
            int_string(data, &header, row.right_offset,
                       row.right_length) != R6_OK ||
            row.left_length < 4 ||
            r6_memcmp(bytes + row.left_offset + row.left_length - 4,
                      ".MED", 4) != 0 ||
            row.right_length < 4 ||
            r6_memcmp(bytes + row.right_offset + row.right_length - 4,
                      ".MED", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int int_function(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_introductory_header_t header;
    uint32_t offset;
    uint32_t length;
    size_t at;
    int result = int_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.function_count) {
        return R6_ERR_ARG;
    }
    at = R6_INT_HEADER_SIZE + R6_INT_ROWS * R6_INT_ROW_SIZE +
         (size_t)index * R6_INT_FUNCTION_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    result = int_string(data, &header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_introductory_parse(const void *data, size_t size,
                          r6_introductory_header_t *out) {
    r6_introductory_header_t header;
    r6_introductory_row_t row;
    uint32_t at;
    int result = int_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.row_count; at++) {
        result = int_row(data, size, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.function_count; at++) {
        char name[64];
        result = int_function(data, size, at, name, sizeof(name));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_introductory_row(const void *data, size_t size, uint32_t index,
                        r6_introductory_row_t *out) {
    return int_row(data, size, index, out);
}

int r6_introductory_name(const void *data, size_t size, uint32_t index,
                         uint32_t slot, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_introductory_row_t row;
    uint32_t offset;
    uint32_t length;
    int result = int_row(data, size, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot >= 2) {
        return R6_ERR_ARG;
    }
    offset = slot == 0u ? row.left_offset : row.right_offset;
    length = slot == 0u ? row.left_length : row.right_length;
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_introductory_function(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity) {
    return int_function(data, size, index, out, capacity);
}
