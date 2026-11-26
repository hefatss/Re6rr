/* Bounded reader for the derived .pdata statistics inventory. */

#include "r6/r6_pdata_stats.h"

#include "core/internal.h"

static const unsigned char pdata_stats_magic[8] = {
    'R', '6', 'P', 'D', 'S', 0, 1, 0
};

enum {
    R6_PDATA_STATS_HEADER_SIZE = 64,
    R6_PDATA_STATS_BUCKET_OFF = 64,
    R6_PDATA_STATS_FUNC_OFF = R6_PDATA_STATS_BUCKET_OFF +
                              R6_PDATA_BUCKETS * 8u,
    R6_PDATA_STATS_STRINGS_OFF = R6_PDATA_STATS_FUNC_OFF +
                                 R6_PDATA_LARGEST * 40u
};

static int pdata_header(const void *data, size_t size,
                        r6_pdata_stats_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pdata_stats_header header;
    if (!bytes || !out || size < R6_PDATA_STATS_HEADER_SIZE ||
        r6_memcmp(bytes, pdata_stats_magic,
                  sizeof(pdata_stats_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != 70377u ||
        r6_u32(bytes, 16) != 14707609u ||
        r6_u32(bytes, 20) != 17273344u ||
        r6_u32(bytes, 24) != 3u ||
        r6_u32(bytes, 28) != 11796u ||
        r6_u32(bytes, 32) != 10367u ||
        r6_u32(bytes, 36) != 2u ||
        r6_u32(bytes, 40) != 60258u ||
        r6_u32(bytes, 44) != 88u ||
        r6_u32(bytes, 48) != R6_PDATA_BUCKETS ||
        r6_u32(bytes, 52) != R6_PDATA_LARGEST ||
        r6_u32(bytes, 60) != R6_PDATA_STATS_STRINGS_OFF ||
        !r6_u32(bytes, 56) ||
        (size_t)R6_PDATA_STATS_STRINGS_OFF + r6_u32(bytes, 56) != size) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.function_count = r6_u32(bytes, 12);
    header.code_bytes = r6_u32(bytes, 16);
    header.text_bytes = r6_u32(bytes, 20);
    header.leaf = r6_u32(bytes, 24);
    header.chained = r6_u32(bytes, 28);
    header.with_eh = r6_u32(bytes, 32);
    header.min_size = r6_u32(bytes, 36);
    header.max_size = r6_u32(bytes, 40);
    header.median = r6_u32(bytes, 44);
    header.bucket_count = r6_u32(bytes, 48);
    header.largest_count = r6_u32(bytes, 52);
    header.strings_size = r6_u32(bytes, 56);
    header.strings_off = r6_u32(bytes, 60);
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int pdata_string(const void *data, size_t size, uint32_t strings_off,
                        uint32_t offset, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t at = offset;
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (offset < strings_off || offset >= size) {
        return R6_ERR_FORMAT;
    }
    while (at < size && bytes[at]) {
        at++;
    }
    if (at == size || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, at - offset);
    out[at - offset] = 0;
    return R6_OK;
}

int r6_pdata_stats_parse(const void *data, size_t size,
                         r6_pdata_stats_header *out) {
    return pdata_header(data, size, out);
}

int r6_pdata_stats_bucket(const void *data, size_t size, uint32_t index,
                          char *label, size_t capacity, uint32_t *count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pdata_stats_header header;
    uint32_t row_off;
    int result = pdata_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.bucket_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_PDATA_STATS_BUCKET_OFF + index * 8u;
    result = pdata_string(data, size, header.strings_off,
                          r6_u32(bytes, row_off), label, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (count) {
        *count = r6_u32(bytes, row_off + 4u);
    }
    return R6_OK;
}

int r6_pdata_stats_largest(const void *data, size_t size, uint32_t index,
                           uint32_t *begin, uint32_t *end,
                           uint32_t *func_size, uint32_t *unwind_rva,
                           uint32_t *flags, uint32_t *leaf,
                           uint32_t *chain_begin, uint32_t *chain_end,
                           uint32_t *chain_unwind, char *section,
                           size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pdata_stats_header header;
    uint32_t row_off;
    uint32_t from;
    uint32_t to;
    uint32_t chain_from;
    uint32_t chain_to;
    int result = pdata_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.largest_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_PDATA_STATS_FUNC_OFF + index * 40u;
    from = r6_u32(bytes, row_off);
    to = r6_u32(bytes, row_off + 4u);
    chain_from = r6_u32(bytes, row_off + 28u);
    chain_to = r6_u32(bytes, row_off + 32u);
    if (from >= to || to > header.text_bytes ||
        r6_u32(bytes, row_off + 8u) != to - from ||
        r6_u32(bytes, row_off + 20u) > 1u ||
        ((chain_from || chain_to) &&
         (!chain_from || !chain_to || chain_from >= chain_to))) {
        return R6_ERR_FORMAT;
    }
    if (section && capacity) {
        result = pdata_string(data, size, header.strings_off,
                              r6_u32(bytes, row_off + 12u), section,
                              capacity);
        if (result != R6_OK) {
            return result;
        }
    }
    if (begin) {
        *begin = from;
    }
    if (end) {
        *end = to;
    }
    if (func_size) {
        *func_size = to - from;
    }
    if (unwind_rva) {
        *unwind_rva = r6_u32(bytes, row_off + 16u);
    }
    if (flags) {
        *flags = r6_u32(bytes, row_off + 24u);
    }
    if (leaf) {
        *leaf = r6_u32(bytes, row_off + 20u);
    }
    if (chain_begin) {
        *chain_begin = chain_from;
    }
    if (chain_end) {
        *chain_end = chain_to;
    }
    if (chain_unwind) {
        *chain_unwind = r6_u32(bytes, row_off + 36u);
    }
    return R6_OK;
}

int r6_pdata_stats_find(const void *data, size_t size, uint32_t begin,
                        uint32_t *index) {
    r6_pdata_stats_header header;
    uint32_t at;
    int result = pdata_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.largest_count; at++) {
        uint32_t found = 0;
        result = r6_pdata_stats_largest(data, size, at, &found, NULL, NULL,
                                        NULL, NULL, NULL, NULL, NULL, NULL,
                                        NULL, 0);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (found == begin) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}
