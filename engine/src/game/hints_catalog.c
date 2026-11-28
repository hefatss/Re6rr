/* Bounds-checked reader for packed hints.dat record facts. */

#include "r6/r6_hints_catalog.h"

#include "core/internal.h"

enum {
    R6_HNT_HEADER_SIZE = 28,
    R6_HNT_ROW_SIZE = 16,
    R6_HNT_ROWS = 67,
    R6_HNT_STRIDE = 16,
    R6_HNT_SOURCE_SIZE = 1072,
    R6_HNT_DISTINCT = 61
};

static const unsigned char hnt_magic[8] = {
    'R', '6', 'H', 'N', 'T', 0, 1, 0
};

static int hnt_header(const void *data, size_t size,
                      r6_hints_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_hints_header_t header;
    size_t expected;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_HNT_HEADER_SIZE ||
            r6_memcmp(bytes, hnt_magic, sizeof(hnt_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_HNT_ROWS ||
            r6_u32(bytes, 16) != R6_HNT_STRIDE ||
            r6_u32(bytes, 20) != R6_HNT_SOURCE_SIZE ||
            r6_u32(bytes, 24) != R6_HNT_DISTINCT) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.record_count = r6_u32(bytes, 12);
    header.stride = r6_u32(bytes, 16);
    header.source_size = r6_u32(bytes, 20);
    header.distinct = r6_u32(bytes, 24);
    expected = R6_HNT_HEADER_SIZE +
               (size_t)header.record_count * R6_HNT_ROW_SIZE;
    if (expected != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_hints_parse(const void *data, size_t size, r6_hints_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_hints_header_t header;
    uint32_t distinct = 0;
    uint32_t at;
    int result = hnt_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.record_count; at++) {
        size_t row = R6_HNT_HEADER_SIZE + (size_t)at * R6_HNT_ROW_SIZE;
        uint32_t earlier;
        for (earlier = 0; earlier < at; earlier++) {
            size_t old = R6_HNT_HEADER_SIZE + (size_t)earlier * R6_HNT_ROW_SIZE;
            if (r6_memcmp(bytes + row, bytes + old, R6_HNT_ROW_SIZE) == 0) {
                break;
            }
        }
        if (earlier == at) {
            distinct++;
        }
        if ((bytes[row + 15] != 0) || distinct > header.distinct) {
            return R6_ERR_FORMAT;
        }
    }
    if (distinct != header.distinct) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_hints_row(const void *data, size_t size, uint32_t index,
                 r6_hints_row_t *out) {
    r6_hints_header_t header;
    int result = hnt_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.record_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(out->words,
              (const unsigned char *)data + R6_HNT_HEADER_SIZE +
                  (size_t)index * R6_HNT_ROW_SIZE,
              R6_HNT_ROW_SIZE);
    return R6_OK;
}
