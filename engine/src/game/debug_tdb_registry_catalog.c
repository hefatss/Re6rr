/* Bounds-checked reader for packed course-debug TDB facts. */

#include "r6/r6_debug_tdb_registry_catalog.h"

#include "core/internal.h"

enum {
    R6_DTR_HEADER_SIZE = 44,
    R6_DTR_FILE_SIZE = 16,
    R6_DTR_PAIR_SIZE = 16,
    R6_DTR_SPAN_SIZE = 8,
    R6_DTR_FILES = 23,
    R6_DTR_PAIRS = 12087,
    R6_DTR_ACCESSORS = 10,
    R6_DTR_BLINKS = 4,
    R6_DTR_TABLE_BYTES = 603341,
    R6_DTR_ACCESSOR_SIZE = 1147,
    R6_DTR_BLINK_SIZE = 384,
    R6_DTR_ID_MIN = 0x10000000,
    R6_DTR_ID_MAX = 0x150000fd,
    R6_DTR_MAX_STRING = 96
};

static const unsigned char dtr_magic[8] = {
    'R', '6', 'D', 'T', 'R', 0, 1, 0
};

static int dtr_header(const void *data, size_t size,
                      r6_debug_tdb_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_debug_tdb_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_DTR_HEADER_SIZE ||
            r6_memcmp(bytes, dtr_magic, sizeof(dtr_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_DTR_FILES ||
            r6_u32(bytes, 16) != R6_DTR_PAIRS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_DTR_TABLE_BYTES ||
            r6_u32(bytes, 28) != R6_DTR_ACCESSORS ||
            r6_u32(bytes, 32) != R6_DTR_ACCESSOR_SIZE ||
            r6_u32(bytes, 36) != R6_DTR_BLINKS ||
            r6_u32(bytes, 40) != R6_DTR_BLINK_SIZE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.pair_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.table_bytes = r6_u32(bytes, 24);
    header.accessor_count = r6_u32(bytes, 28);
    header.accessor_size = r6_u32(bytes, 32);
    header.blink_count = r6_u32(bytes, 36);
    header.blink_size = r6_u32(bytes, 40);
    base = R6_DTR_HEADER_SIZE +
           (size_t)header.file_count * R6_DTR_FILE_SIZE +
           (size_t)header.pair_count * R6_DTR_PAIR_SIZE +
           (size_t)(header.accessor_count + header.blink_count) *
               R6_DTR_SPAN_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t dtr_pair_base(void) {
    return R6_DTR_HEADER_SIZE + R6_DTR_FILES * R6_DTR_FILE_SIZE;
}

static size_t dtr_span_base(void) {
    return dtr_pair_base() + R6_DTR_PAIRS * R6_DTR_PAIR_SIZE;
}

static size_t dtr_string_base(void) {
    return dtr_span_base() +
           (R6_DTR_ACCESSORS + R6_DTR_BLINKS) * R6_DTR_SPAN_SIZE;
}

static int dtr_string(const void *data,
                      const r6_debug_tdb_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = dtr_string_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_DTR_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (value < 0x20u || value > 0x7eu) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int dtr_copy(const void *data,
                    const r6_debug_tdb_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = dtr_string(data, header, offset, length);
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

static int dtr_file(const void *data, size_t size, uint32_t index,
                    r6_debug_tdb_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_debug_tdb_header_t header;
    r6_debug_tdb_file_t file;
    size_t at;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_DTR_HEADER_SIZE + (size_t)index * R6_DTR_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.pairs || file.pairs > header.pair_count ||
            file.path_length < 4 ||
            dtr_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int dtr_pair(const void *data, size_t size, uint32_t index,
                    r6_debug_tdb_pair_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_debug_tdb_header_t header;
    r6_debug_tdb_pair_t pair;
    size_t at;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.pair_count || !out) {
        return R6_ERR_ARG;
    }
    at = dtr_pair_base() + (size_t)index * R6_DTR_PAIR_SIZE;
    r6_memcpy(&pair, bytes + at, sizeof(pair));
    if (pair.id != pair.decimal || pair.id < R6_DTR_ID_MIN ||
            pair.id > R6_DTR_ID_MAX || pair.name_length < 2 ||
            dtr_string(data, &header, pair.name_offset,
                       pair.name_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &pair, sizeof(pair));
    return R6_OK;
}

static int dtr_span(const void *data, size_t size, uint32_t index,
                    uint32_t *offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_debug_tdb_header_t header;
    size_t at;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.accessor_count + header.blink_count || !offset ||
            !length) {
        return R6_ERR_ARG;
    }
    at = dtr_span_base() + (size_t)index * R6_DTR_SPAN_SIZE;
    *offset = r6_u32(bytes, at);
    *length = r6_u32(bytes, at + 4);
    return dtr_string(data, &header, *offset, *length);
}

static int dtr_copy_span(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    r6_debug_tdb_header_t header;
    uint32_t offset = 0;
    uint32_t length = 0;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = dtr_span(data, size, index, &offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return dtr_copy(data, &header, offset, length, out, capacity);
}

int r6_debug_tdb_parse(const void *data, size_t size,
                       r6_debug_tdb_header_t *out) {
    r6_debug_tdb_header_t header;
    r6_debug_tdb_file_t file;
    r6_debug_tdb_pair_t pair;
    char text[R6_DTR_MAX_STRING + 1];
    uint32_t pairs = 0;
    uint32_t bytes = 0;
    uint32_t at;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = dtr_file(data, size, at, &file);
        if (result != R6_OK || file.pairs > header.pair_count - pairs) {
            return R6_ERR_FORMAT;
        }
        pairs += file.pairs;
        bytes += file.size;
    }
    if (pairs != header.pair_count || bytes != header.table_bytes) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.pair_count; at++) {
        result = dtr_pair(data, size, at, &pair);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.blink_count + header.accessor_count; at++) {
        result = dtr_copy_span(data, size, at, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
        if (at >= header.blink_count &&
                (at - header.blink_count >= header.accessor_count ||
                 r6_memcmp(text, "GetDebug", 8) != 0)) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_debug_tdb_file(const void *data, size_t size, uint32_t index,
                      r6_debug_tdb_file_t *out) {
    return dtr_file(data, size, index, out);
}

int r6_debug_tdb_path(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_debug_tdb_header_t header;
    r6_debug_tdb_file_t file;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = dtr_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return dtr_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_debug_tdb_pair(const void *data, size_t size, uint32_t index,
                      r6_debug_tdb_pair_t *out) {
    return dtr_pair(data, size, index, out);
}

int r6_debug_tdb_blink(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    r6_debug_tdb_header_t header;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.blink_count) {
        return R6_ERR_ARG;
    }
    return dtr_copy_span(data, size, index, out, capacity);
}

int r6_debug_tdb_accessor(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity) {
    r6_debug_tdb_header_t header;
    int result = dtr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.accessor_count) {
        return R6_ERR_ARG;
    }
    return dtr_copy_span(data, size, header.blink_count + index, out,
                         capacity);
}
