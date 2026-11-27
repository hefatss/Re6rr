/* Bounds-checked reader for the packed drive_story_* key namespace. Only
 * copied keys and observed source facts cross the bridge. */

#include "r6/r6_story_key_namespace.h"

#include "core/internal.h"

static const unsigned char namespace_magic[8] = {
    'R', '6', 'S', 'K', 'N', 0, 1, 0
};

static int namespace_layout(const void *data, size_t size,
                            r6_story_key_namespace_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_story_key_namespace_header_t header;
    size_t records;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_STORY_KEY_NAMESPACE_HEADER_SIZE ||
            r6_memcmp(bytes, namespace_magic, sizeof(namespace_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.count = r6_u32(bytes, 12);
    header.native_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.header_size = r6_u32(bytes, 24);
    header.strings_offset = r6_u32(bytes, 28);
    header.reserved = r6_u32(bytes, 32);
    if (!header.count || !header.string_size ||
            header.native_count > header.count ||
            header.header_size != R6_STORY_KEY_NAMESPACE_HEADER_SIZE ||
            header.strings_offset != header.header_size +
            (size_t)header.count * R6_STORY_KEY_NAMESPACE_RECORD_SIZE ||
            header.reserved ||
            header.count > ((size_t)-1 - header.header_size) /
                           R6_STORY_KEY_NAMESPACE_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    records = (size_t)header.count * R6_STORY_KEY_NAMESPACE_RECORD_SIZE;
    if (header.header_size + records > size ||
            header.strings_offset > size ||
            header.string_size != size - header.strings_offset) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int namespace_row(const void *data, size_t size, uint32_t index,
                         const unsigned char **bytes, size_t *row_off) {
    r6_story_key_namespace_header_t header;
    int result = namespace_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = header.header_size +
               (size_t)index * R6_STORY_KEY_NAMESPACE_RECORD_SIZE;
    return R6_OK;
}

static int namespace_string(const void *data, size_t size, uint32_t offset,
                            char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_story_key_namespace_header_t header;
    size_t end;
    uint32_t at;
    int result = namespace_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    end = header.strings_offset + header.string_size;
    if (offset < header.strings_offset || offset >= end) {
        return R6_ERR_FORMAT;
    }
    at = offset;
    while (at < end && bytes[at]) {
        at++;
    }
    if (at == end || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, at - offset);
    out[at - offset] = 0;
    return R6_OK;
}

int r6_story_key_namespace_parse(const void *data, size_t size,
                                 r6_story_key_namespace_header_t *out) {
    return namespace_layout(data, size, out);
}

int r6_story_key_namespace_name(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    int result = namespace_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    return namespace_string(data, size, r6_u32(bytes, row), out, capacity);
}

int r6_story_key_namespace_find(const void *data, size_t size,
                                const char *name) {
    r6_story_key_namespace_header_t header;
    const unsigned char *bytes;
    size_t length;
    uint32_t at;
    if (namespace_layout(data, size, &header) != R6_OK || !name) {
        return -1;
    }
    length = r6_strlen(name);
    bytes = (const unsigned char *)data;
    for (at = 0; at < header.count; at++) {
        size_t row = header.header_size +
                     (size_t)at * R6_STORY_KEY_NAMESPACE_RECORD_SIZE;
        uint32_t offset = r6_u32(bytes, row);
        uint32_t stored = r6_u32(bytes, row + 4);
        if (stored != length || offset < header.strings_offset ||
                offset >= header.strings_offset + header.string_size ||
                length > header.strings_offset + header.string_size - offset) {
            continue;
        }
        if (r6_memcmp(bytes + offset, name, length) == 0) {
            return (int)at;
        }
    }
    return -1;
}

int r6_story_key_namespace_fact(const void *data, size_t size, uint32_t index,
                                uint32_t *source, uint32_t *table_index) {
    const unsigned char *bytes;
    size_t row;
    uint32_t got_source;
    uint32_t got_table;
    int result = namespace_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!source || !table_index) {
        return R6_ERR_ARG;
    }
    got_source = bytes[row + 8];
    got_table = r6_u32(bytes, row + 12);
    if ((got_source != R6_STORY_KEY_NAMESPACE_MSGDB_ONLY &&
         got_source != R6_STORY_KEY_NAMESPACE_DIRECT &&
         got_source != R6_STORY_KEY_NAMESPACE_TABLE) ||
            (got_source == R6_STORY_KEY_NAMESPACE_TABLE ?
             got_table >= 100u :
             got_table != R6_STORY_KEY_NAMESPACE_NO_TABLE)) {
        return R6_ERR_FORMAT;
    }
    *source = got_source;
    *table_index = got_table;
    return R6_OK;
}
