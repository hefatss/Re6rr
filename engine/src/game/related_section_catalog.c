/* Bounds-checked reader for packed related-section facts. */

#include "r6/r6_related_section_catalog.h"

#include "core/internal.h"

enum {
    R6_RSH_HEADER_SIZE = 32,
    R6_RSH_FILE_SIZE = 24,
    R6_RSH_PAIR_SIZE = 48,
    R6_RSH_FILES = 5,
    R6_RSH_PAIRS = 540,
    R6_RSH_MAX_ID = 604
};

static const unsigned char rsh_magic[8] = {
    'R', '6', 'R', 'S', 'H', 0, 1, 0
};

static int rsh_header(const void *data, size_t size,
                      r6_related_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_related_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_RSH_HEADER_SIZE ||
            r6_memcmp(bytes, rsh_magic, sizeof(rsh_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_RSH_FILES ||
            !r6_u32(bytes, 16) || r6_u32(bytes, 20) != R6_RSH_PAIRS ||
            r6_u32(bytes, 24) != 5u || r6_u32(bytes, 28) != 5u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.pair_count = r6_u32(bytes, 20);
    header.load_speed_0 = 5u;
    header.load_speed_1 = 5u;
    base = R6_RSH_HEADER_SIZE +
           (size_t)header.file_count * R6_RSH_FILE_SIZE +
           (size_t)header.string_size +
           (size_t)header.pair_count * R6_RSH_PAIR_SIZE;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t rsh_string_base(const r6_related_header_t *header) {
    return R6_RSH_HEADER_SIZE +
           (size_t)header->file_count * R6_RSH_FILE_SIZE;
}

static size_t rsh_pair_base(const r6_related_header_t *header) {
    return rsh_string_base(header) + header->string_size;
}

static int rsh_string(const void *data, const r6_related_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = rsh_string_base(header);
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > 96 || (size_t)offset < base ||
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

static int rsh_file(const void *data, size_t size, uint32_t index,
                    r6_related_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_related_header_t header;
    r6_related_file_t file;
    size_t at;
    int result = rsh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_RSH_HEADER_SIZE + (size_t)index * R6_RSH_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.pairs || file.pairs > header.pair_count ||
            file.load_speed_0 != 5u || file.load_speed_1 != 5u ||
            file.path_length < 4 ||
            rsh_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int rsh_pair(const void *data, size_t size, uint32_t index,
                    r6_related_pair_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_related_header_t header;
    size_t at;
    size_t word;
    int result = rsh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.pair_count || !out) {
        return R6_ERR_ARG;
    }
    at = rsh_pair_base(&header) + (size_t)index * R6_RSH_PAIR_SIZE;
    r6_memcpy(out->values, bytes + at, R6_RSH_PAIR_SIZE);
    for (word = 0; word < 12; word++) {
        if (out->values[word] > R6_RSH_MAX_ID) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

int r6_related_parse(const void *data, size_t size,
                     r6_related_header_t *out) {
    r6_related_header_t header;
    r6_related_file_t file;
    r6_related_pair_t pair;
    uint32_t pairs = 0;
    uint32_t at;
    int result = rsh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = rsh_file(data, size, at, &file);
        if (result != R6_OK || file.pairs > header.pair_count - pairs) {
            return R6_ERR_FORMAT;
        }
        pairs += file.pairs;
    }
    if (pairs != header.pair_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.pair_count; at++) {
        result = rsh_pair(data, size, at, &pair);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_related_file(const void *data, size_t size, uint32_t index,
                    r6_related_file_t *out) {
    return rsh_file(data, size, index, out);
}

int r6_related_path(const void *data, size_t size, uint32_t index,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_related_file_t file;
    int result = rsh_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)file.path_length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + file.path_offset, file.path_length);
    out[file.path_length] = 0;
    return R6_OK;
}

int r6_related_pair(const void *data, size_t size, uint32_t index,
                    r6_related_pair_t *out) {
    return rsh_pair(data, size, index, out);
}
