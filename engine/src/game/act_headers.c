/* Bounds-checked reader for raw .ACT header prefixes. No files are opened and
 * no bytes beyond the copied prefix are interpreted. */

#include "r6/r6_act_headers.h"

#include "core/internal.h"

enum {
    R6_ACT_HEADER_SIZE = 24,
    R6_ACT_RECORD_SIZE = 76
};

static const unsigned char act_magic[8] = {
    'R', '6', 'A', 'C', 'T', 0, 1, 0
};

static int act_layout(const void *data, size_t size, r6_act_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_act_header header;
    uint32_t count;
    size_t records;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_ACT_HEADER_SIZE ||
            r6_memcmp(bytes, act_magic, sizeof(act_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 16) != R6_ACT_PREFIX_SIZE) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(bytes, 12);
    if (count > ((size_t)-1 - R6_ACT_HEADER_SIZE) / R6_ACT_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    records = (size_t)count * R6_ACT_RECORD_SIZE;
    header.strings_size = r6_u32(bytes, 20);
    if ((size_t)R6_ACT_HEADER_SIZE + records > size ||
            (size_t)header.strings_size !=
            size - R6_ACT_HEADER_SIZE - records) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.count = count;
    header.prefix_size = R6_ACT_PREFIX_SIZE;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int act_row(const void *data, size_t size, uint32_t index,
                   const unsigned char **bytes, size_t *row_off,
                   uint32_t *strings_size) {
    r6_act_header header;
    int result = act_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = R6_ACT_HEADER_SIZE + (size_t)index * R6_ACT_RECORD_SIZE;
    *strings_size = header.strings_size;
    return R6_OK;
}

int r6_act_parse(const void *data, size_t size, r6_act_header *out) {
    return act_layout(data, size, out);
}

int r6_act_size(const void *data, size_t size, uint32_t index,
                uint32_t *file_size) {
    const unsigned char *bytes;
    size_t row;
    uint32_t strings_size;
    int result = act_row(data, size, index, &bytes, &row, &strings_size);
    if (result != R6_OK) {
        return result;
    }
    if (!file_size) {
        return R6_ERR_ARG;
    }
    *file_size = r6_u32(bytes, row + 8);
    return R6_OK;
}

int r6_act_path(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    size_t strings_off;
    uint32_t strings_size;
    uint32_t offset;
    uint32_t length;
    size_t at;
    int result = act_row(data, size, index, &bytes, &row, &strings_size);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    strings_off = R6_ACT_HEADER_SIZE +
                  (size_t)r6_u32(bytes, 12) * R6_ACT_RECORD_SIZE;
    offset = r6_u32(bytes, row);
    length = r6_u32(bytes, row + 4);
    if (!length || offset > strings_size ||
            length > strings_size - offset ||
            bytes[strings_off + offset + length]) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        if (!bytes[strings_off + offset + at]) {
            return R6_ERR_FORMAT;
        }
    }
    if (capacity <= length) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + strings_off + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_act_prefix(const void *data, size_t size, uint32_t index,
                  unsigned char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    uint32_t strings_size;
    int result = act_row(data, size, index, &bytes, &row, &strings_size);
    if (result != R6_OK) {
        return result;
    }
    if (!out || capacity < R6_ACT_PREFIX_SIZE) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + row + 12, R6_ACT_PREFIX_SIZE);
    return R6_OK;
}
