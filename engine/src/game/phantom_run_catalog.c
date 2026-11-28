/* Bounds-checked reader for the packed phantom run inventory. */

#include "r6/r6_phantom_run_catalog.h"

#include "core/internal.h"

enum {
    R6_PHM_HEADER_SIZE = 52,
    R6_PHM_TIMESTAMPS = 5,
    R6_PHM_RECORDS = 2333,
    R6_PHM_SOURCE = 18728
};

static const unsigned char phm_magic[8] = {
    'R', '6', 'P', 'H', 'M', 0, 1, 0
};

static const uint32_t phm_words[6] = {
    1573408u, 1u, 13u, 21u, 5u, 311u
};

static int phm_header(const void *data, size_t size,
                      r6_phantom_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_phantom_header_t header;
    uint32_t at;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_PHM_HEADER_SIZE ||
            r6_memcmp(bytes, phm_magic, sizeof(phm_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_PHM_RECORDS ||
            r6_u32(bytes, 20) != R6_PHM_TIMESTAMPS ||
            r6_u32(bytes, 24) != R6_PHM_SOURCE ||
            size != R6_PHM_HEADER_SIZE + R6_PHM_TIMESTAMPS * 8u +
                   R6_PHM_RECORDS * 8u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.record_count = R6_PHM_RECORDS;
    header.timestamp_count = R6_PHM_TIMESTAMPS;
    header.source_bytes = R6_PHM_SOURCE;
    for (at = 0; at < 6; at++) {
        header.words[at] = r6_u32(bytes, 28 + (size_t)at * 4);
        if (header.words[at] != phm_words[at]) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static uint64_t phm_word(const void *data, size_t offset) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint64_t value = 0;
    uint32_t at;
    for (at = 0; at < 8; at++) {
        value |= (uint64_t)bytes[offset + at] << (at * 8u);
    }
    return value;
}

int r6_phantom_parse(const void *data, size_t size,
                     r6_phantom_header_t *out) {
    return phm_header(data, size, out);
}

int r6_phantom_timestamp(const void *data, size_t size, uint32_t index,
                         uint64_t *out) {
    r6_phantom_header_t header;
    int result = phm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.timestamp_count || !out) {
        return R6_ERR_ARG;
    }
    *out = phm_word(data, R6_PHM_HEADER_SIZE + (size_t)index * 8u);
    return R6_OK;
}

int r6_phantom_record(const void *data, size_t size, uint32_t index,
                      uint64_t *out) {
    r6_phantom_header_t header;
    int result = phm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.record_count || !out) {
        return R6_ERR_ARG;
    }
    *out = phm_word(data, R6_PHM_HEADER_SIZE +
                    R6_PHM_TIMESTAMPS * 8u + (size_t)index * 8u);
    return R6_OK;
}
