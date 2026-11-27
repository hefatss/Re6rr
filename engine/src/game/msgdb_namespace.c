/* Bounds-checked reader for the packed msgdb.lua MessageID namespace. Only
 * copied keys, offsets and group indices cross the bridge. The group offset
 * table makes all accessors O(1) apart from first-exact find(). */

#include "r6/r6_msgdb_namespace.h"

#include "core/internal.h"

enum {
    R6_MSGDB_HEADER_SIZE = 32,
    R6_MSGDB_RECORD_SIZE = 16,
    R6_MSGDB_GROUP_SIZE = 4
};

static const unsigned char msgdb_magic[8] = {
    'R', '6', 'M', 'N', 'S', 0, 1, 0
};

static size_t msgdb_group_table(const r6_msgdb_header_t *header) {
    return R6_MSGDB_HEADER_SIZE +
           (size_t)header->count * R6_MSGDB_RECORD_SIZE;
}

static size_t msgdb_string_base(const r6_msgdb_header_t *header) {
    return msgdb_group_table(header) +
           (size_t)header->group_count * R6_MSGDB_GROUP_SIZE;
}

static int msgdb_header(const void *data, size_t size,
                        r6_msgdb_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msgdb_header_t header;
    size_t records;
    size_t groups;
    size_t base;
    size_t end;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_MSGDB_HEADER_SIZE ||
            r6_memcmp(bytes, msgdb_magic, sizeof(msgdb_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.count = r6_u32(bytes, 12);
    header.group_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.msgdb_size = r6_u32(bytes, 24);
    header.story_count = r6_u32(bytes, 28);
    if (!header.count || !header.group_count || !header.string_size ||
            !header.msgdb_size ||
            header.count > ((size_t)-1 - R6_MSGDB_HEADER_SIZE -
                            (size_t)header.group_count *
                            R6_MSGDB_GROUP_SIZE) / R6_MSGDB_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    records = (size_t)header.count * R6_MSGDB_RECORD_SIZE;
    groups = (size_t)header.group_count * R6_MSGDB_GROUP_SIZE;
    if (groups > (size_t)-1 - R6_MSGDB_HEADER_SIZE - records) {
        return R6_ERR_FORMAT;
    }
    base = R6_MSGDB_HEADER_SIZE + records + groups;
    end = base + header.string_size;
    if (end < base || end != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int msgdb_copy(const void *data, const r6_msgdb_header_t *header,
                      uint32_t offset, uint32_t length, char *out,
                      size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = msgdb_string_base(header);
    size_t end = base + header->string_size;
    size_t at;
    if (!out) {
        return R6_ERR_ARG;
    }
    if (length >= capacity) {
        return R6_ERR_BUFFER;
    }
    if ((size_t)offset < base || (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < length; at++) {
        if (bytes[(size_t)offset + at] >= 0x80u) {
            return R6_ERR_FORMAT;
        }
    }
    if (bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int msgdb_layout(const void *data, size_t size,
                        r6_msgdb_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msgdb_header_t header;
    uint32_t previous_source = 0;
    uint32_t previous_group = 0;
    uint32_t story = 0;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = msgdb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.group_count; at++) {
        size_t row = msgdb_group_table(&header) +
                     (size_t)at * R6_MSGDB_GROUP_SIZE;
        char name[R6_MSGDB_GROUP_LENGTH + 1];
        result = msgdb_copy(data, &header, r6_u32(bytes, row),
                            R6_MSGDB_GROUP_LENGTH, name, sizeof(name));
        if (result != R6_OK || r6_strlen(name) != R6_MSGDB_GROUP_LENGTH ||
                (at && r6_u32(bytes, row) <= previous_group)) {
            return R6_ERR_FORMAT;
        }
        previous_group = r6_u32(bytes, row);
    }
    for (at = 0; at < header.count; at++) {
        size_t row = R6_MSGDB_HEADER_SIZE +
                     (size_t)at * R6_MSGDB_RECORD_SIZE;
        uint32_t offset = r6_u32(bytes, row);
        uint32_t length = r6_u32(bytes, row + 4);
        uint32_t source = r6_u32(bytes, row + 8);
        uint32_t group = r6_u32(bytes, row + 12);
        size_t group_row = msgdb_group_table(&header) +
                           (size_t)group * R6_MSGDB_GROUP_SIZE;
        char group_name[R6_MSGDB_GROUP_LENGTH + 1];
        if (length < R6_MSGDB_GROUP_LENGTH || source >= header.msgdb_size ||
                group >= header.group_count ||
                (at && source <= previous_source)) {
            return R6_ERR_FORMAT;
        }
        {
            size_t base = msgdb_string_base(&header);
            size_t end = base + header.string_size;
            size_t cursor;
            if ((size_t)offset < base || (size_t)offset >= end ||
                    (size_t)length > end - (size_t)offset - 1u) {
                return R6_ERR_FORMAT;
            }
            for (cursor = 0; cursor < length; cursor++) {
                if (bytes[(size_t)offset + cursor] >= 0x80u) {
                    return R6_ERR_FORMAT;
                }
            }
            if (bytes[(size_t)offset + length] != 0) {
                return R6_ERR_FORMAT;
            }
        }
        result = msgdb_copy(data, &header, r6_u32(bytes, group_row),
                            R6_MSGDB_GROUP_LENGTH, group_name,
                            sizeof(group_name));
        if (result != R6_OK ||
                r6_memcmp(bytes + offset, group_name,
                          R6_MSGDB_GROUP_LENGTH) != 0) {
            return R6_ERR_FORMAT;
        }
        previous_source = source;
        if (length >= 12 &&
                r6_memcmp(bytes + offset, "drive_story_", 12) == 0) {
            story++;
        }
    }
    if (story != header.story_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_msgdb_namespace_parse(const void *data, size_t size,
                             r6_msgdb_header_t *out) {
    return msgdb_layout(data, size, out);
}

int r6_msgdb_namespace_key(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msgdb_header_t header;
    size_t row;
    int result = msgdb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count) {
        return R6_ERR_ARG;
    }
    row = R6_MSGDB_HEADER_SIZE + (size_t)index * R6_MSGDB_RECORD_SIZE;
    return msgdb_copy(data, &header, r6_u32(bytes, row),
                      r6_u32(bytes, row + 4), out, capacity);
}

int r6_msgdb_namespace_find(const void *data, size_t size, const char *key) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msgdb_header_t header;
    size_t length;
    size_t base;
    size_t end;
    uint32_t at;
    if (msgdb_header(data, size, &header) != R6_OK || !key) {
        return -1;
    }
    length = r6_strlen(key);
    base = msgdb_string_base(&header);
    end = base + header.string_size;
    for (at = 0; at < header.count; at++) {
        size_t row = R6_MSGDB_HEADER_SIZE +
                     (size_t)at * R6_MSGDB_RECORD_SIZE;
        uint32_t offset = r6_u32(bytes, row);
        uint32_t stored = r6_u32(bytes, row + 4);
        if (stored != length || (size_t)offset < base ||
                (size_t)offset >= end || length > end - (size_t)offset ||
                r6_memcmp(bytes + offset, key, length) != 0) {
            continue;
        }
        return (int)at;
    }
    return -1;
}

int r6_msgdb_namespace_fact(const void *data, size_t size, uint32_t index,
                            uint32_t *byte_offset, uint32_t *group_index) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msgdb_header_t header;
    size_t row;
    int result = msgdb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count || !byte_offset || !group_index) {
        return R6_ERR_ARG;
    }
    row = R6_MSGDB_HEADER_SIZE + (size_t)index * R6_MSGDB_RECORD_SIZE;
    *byte_offset = r6_u32(bytes, row + 8);
    *group_index = r6_u32(bytes, row + 12);
    return R6_OK;
}

int r6_msgdb_namespace_group(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_msgdb_header_t header;
    size_t row;
    int result = msgdb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.group_count) {
        return R6_ERR_ARG;
    }
    row = msgdb_group_table(&header) +
          (size_t)index * R6_MSGDB_GROUP_SIZE;
    return msgdb_copy(data, &header, r6_u32(bytes, row),
                      R6_MSGDB_GROUP_LENGTH, out, capacity);
}
