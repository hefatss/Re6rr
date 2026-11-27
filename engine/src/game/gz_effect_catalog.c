/* Bounds-checked reader for stage-effect gzip header facts. Only copied
 * paths, sizes and 16-byte inflated prefixes cross the bridge. */

#include "r6/r6_gz_effect_catalog.h"

#include "core/internal.h"

enum {
    R6_GZ_EFFECT_HEADER_SIZE = 36,
    R6_GZ_EFFECT_FILE_SIZE = 60
};

static const unsigned char gz_effect_magic[8] = {
    'R', '6', 'G', 'E', 'F', 0, 1, 0
};

static const unsigned char gz_known[4][4] = {
    {'N', 'D', 'W', 'D'}, {'N', 'T', 'W', 'D'},
    {'N', 'D', 'L', 'X'}, {'N', 'T', 'L', 'X'}
};

static size_t gz_effect_string_base(const r6_gz_effect_header_t *header) {
    return R6_GZ_EFFECT_HEADER_SIZE +
           (size_t)header->file_count * R6_GZ_EFFECT_FILE_SIZE;
}

static int gz_effect_layout(const void *data, size_t size,
                            r6_gz_effect_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_gz_effect_header_t header;
    size_t strings;
    size_t expected;
    uint32_t at;
    uint32_t flags0 = 0;
    uint32_t flags8 = 0;
    uint32_t known = 0;
    uint32_t other = 0;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_GZ_EFFECT_HEADER_SIZE ||
            r6_memcmp(bytes, gz_effect_magic, sizeof(gz_effect_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.flag0_count = r6_u32(bytes, 20);
    header.flag8_count = r6_u32(bytes, 24);
    header.known_count = r6_u32(bytes, 28);
    header.other_count = r6_u32(bytes, 32);
    if (!header.file_count || !header.string_size ||
            header.file_count > ((size_t)-1 - R6_GZ_EFFECT_HEADER_SIZE) /
                                R6_GZ_EFFECT_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    strings = (size_t)header.file_count * R6_GZ_EFFECT_FILE_SIZE;
    expected = R6_GZ_EFFECT_HEADER_SIZE + strings + header.string_size;
    if (expected < R6_GZ_EFFECT_HEADER_SIZE + strings || expected != size ||
            header.flag0_count + (size_t)header.flag8_count !=
            header.file_count ||
            header.known_count + (size_t)header.other_count !=
            header.file_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.file_count; at++) {
        size_t row = R6_GZ_EFFECT_HEADER_SIZE +
                     (size_t)at * R6_GZ_EFFECT_FILE_SIZE;
        uint32_t offset = r6_u32(bytes, row);
        uint32_t length = r6_u32(bytes, row + 4);
        uint32_t flags = r6_u32(bytes, row + 12);
        uint32_t inflated = r6_u32(bytes, row + 32);
        uint32_t header_size = r6_u32(bytes, row + 36);
        uint32_t prefix_length = r6_u32(bytes, row + 40);
        size_t strings_off = gz_effect_string_base(&header);
        size_t end = strings_off + header.string_size;
        size_t cursor;
        int recognized = 0;
        uint32_t kind;
        if (!length || offset < strings_off || offset >= end ||
                (size_t)offset + length >= end) {
            return R6_ERR_FORMAT;
        }
        cursor = offset;
        while (cursor < end && bytes[cursor]) {
            cursor++;
        }
        if (cursor != (size_t)offset + length) {
            return R6_ERR_FORMAT;
        }
        if (flags == 0u) {
            flags0++;
        } else if (flags == 8u) {
            flags8++;
        } else {
            return R6_ERR_FORMAT;
        }
        if (!inflated || header_size < 10u ||
                r6_u32(bytes, row + 8) < header_size + 8u ||
                r6_u32(bytes, row + 28) != inflated ||
                prefix_length > R6_GZ_EFFECT_PREFIX_SIZE ||
                prefix_length != (inflated < R6_GZ_EFFECT_PREFIX_SIZE ?
                                  inflated : R6_GZ_EFFECT_PREFIX_SIZE)) {
            return R6_ERR_FORMAT;
        }
        for (kind = 0; kind < 4; kind++) {
            if (prefix_length >= 4 &&
                    r6_memcmp(bytes + row + 44, gz_known[kind], 4) == 0) {
                recognized = 1;
            }
        }
        if (recognized) {
            known++;
        } else {
            other++;
        }
        for (cursor = row + 44 + prefix_length;
             cursor < row + 44 + R6_GZ_EFFECT_PREFIX_SIZE; cursor++) {
            if (bytes[cursor]) {
                return R6_ERR_FORMAT;
            }
        }
    }
    if (flags0 != header.flag0_count || flags8 != header.flag8_count ||
            known != header.known_count || other != header.other_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int gz_effect_row(const void *data, size_t size, uint32_t index,
                         const r6_gz_effect_header_t *header, size_t *row) {
    if (index >= header->file_count) {
        return R6_ERR_ARG;
    }
    (void)data;
    (void)size;
    *row = R6_GZ_EFFECT_HEADER_SIZE +
           (size_t)index * R6_GZ_EFFECT_FILE_SIZE;
    return R6_OK;
}

int r6_gz_effect_parse(const void *data, size_t size,
                       r6_gz_effect_header_t *out) {
    return gz_effect_layout(data, size, out);
}

int r6_gz_effect_file(const void *data, size_t size, uint32_t index,
                      r6_gz_effect_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_gz_effect_header_t header;
    size_t row;
    int result = gz_effect_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = gz_effect_row(data, size, index, &header, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + row, sizeof(*out));
    return R6_OK;
}

int r6_gz_effect_path(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_gz_effect_header_t header;
    size_t row;
    uint32_t offset;
    uint32_t length;
    size_t cursor;
    int result = gz_effect_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = gz_effect_row(data, size, index, &header, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, row);
    length = r6_u32(bytes, row + 4);
    cursor = offset;
    while (cursor < gz_effect_string_base(&header) + header.string_size &&
           bytes[cursor]) {
        cursor++;
    }
    if (cursor != (size_t)offset + length || cursor - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, cursor - offset);
    out[cursor - offset] = 0;
    return R6_OK;
}
