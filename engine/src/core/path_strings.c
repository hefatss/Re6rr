/* Bounded reader for the derived executable/source path string inventory. */

#include "r6/r6_path_strings.h"

#include "core/internal.h"

static const unsigned char path_strings_magic[8] = {
    'R', '6', 'P', 'S', 'T', 0, 1, 0
};

enum {
    R6_PATH_STRINGS_HEADER_SIZE = 24,
    R6_PATH_STRINGS_GROUP_OFF = 24,
    R6_PATH_STRINGS_WORD_OFF = R6_PATH_STRINGS_GROUP_OFF +
                               R6_PATH_STRINGS_GROUPS * 12u,
    R6_PATH_STRINGS_STRING_OFF = R6_PATH_STRINGS_WORD_OFF +
                                 R6_PATH_STRINGS_COUNT * 4u
};

static int path_header(const void *data, size_t size,
                       r6_path_strings_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_path_strings_header header;
    if (!bytes || !out || size < R6_PATH_STRINGS_HEADER_SIZE ||
        r6_memcmp(bytes, path_strings_magic,
                  sizeof(path_strings_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_PATH_STRINGS_GROUPS ||
        r6_u32(bytes, 16) != R6_PATH_STRINGS_COUNT) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.group_count = r6_u32(bytes, 12);
    header.string_count = r6_u32(bytes, 16);
    header.strings_size = r6_u32(bytes, 20);
    if (!header.strings_size ||
        (size_t)R6_PATH_STRINGS_STRING_OFF + header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int path_string(const void *data, size_t size, uint32_t offset,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t at = offset;
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (offset < R6_PATH_STRINGS_STRING_OFF || offset >= size) {
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

int r6_path_strings_parse(const void *data, size_t size,
                          r6_path_strings_header *out) {
    return path_header(data, size, out);
}

int r6_path_strings_group(const void *data, size_t size, uint32_t index,
                          uint32_t *kind, uint32_t *count, uint32_t *first) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_path_strings_header header;
    uint32_t row_off;
    uint32_t kind_value;
    uint32_t number;
    int result = path_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.group_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_PATH_STRINGS_GROUP_OFF + index * 12u;
    kind_value = r6_u32(bytes, row_off);
    number = r6_u32(bytes, row_off + 4u);
    if (kind_value > R6_PATH_STRINGS_SOURCE ||
        r6_u32(bytes, row_off + 8u) + number > header.string_count ||
        (index == 0 && (kind_value != R6_PATH_STRINGS_EXE ||
                        number != 1271)) ||
        (index == 1 && (kind_value != R6_PATH_STRINGS_SOURCE ||
                        number != 422))) {
        return R6_ERR_FORMAT;
    }
    if (kind) {
        *kind = kind_value;
    }
    if (count) {
        *count = number;
    }
    if (first) {
        *first = r6_u32(bytes, row_off + 8u);
    }
    return R6_OK;
}

int r6_path_strings_get(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_path_strings_header header;
    uint32_t offset;
    int result = path_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.string_count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, R6_PATH_STRINGS_WORD_OFF + index * 4u);
    return path_string(data, size, offset, out, capacity);
}

int r6_path_strings_group_get(const void *data, size_t size,
                              uint32_t group_index, uint32_t local_index,
                              char *out, size_t capacity) {
    uint32_t first = 0;
    uint32_t count = 0;
    int result = r6_path_strings_group(data, size, group_index, NULL, &count,
                                       &first);
    if (result != R6_OK) {
        return result;
    }
    if (local_index >= count) {
        return R6_ERR_ARG;
    }
    return r6_path_strings_get(data, size, first + local_index, out,
                               capacity);
}

int r6_path_strings_find(const void *data, size_t size, const char *text,
                         uint32_t *group_index, uint32_t *local_index,
                         uint32_t *global_index) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_path_strings_header header;
    size_t wanted;
    uint32_t group = 0;
    uint32_t first = 0;
    uint32_t global = 0;
    uint32_t local;
    int result = path_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!text) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(text);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (; group < header.group_count; group++) {
        uint32_t count = 0;
        result = r6_path_strings_group(data, size, group, NULL, &count,
                                       &first);
        if (result != R6_OK) {
            return result;
        }
        for (local = 0; local < count; local++) {
            uint32_t offset = r6_u32(bytes, R6_PATH_STRINGS_WORD_OFF +
                                           global * 4u);
            uint32_t end = offset;
            while (end < size && bytes[end]) {
                end++;
            }
            if (end < size && end - offset == wanted &&
                r6_memcmp(bytes + offset, text, wanted) == 0) {
                if (group_index) {
                    *group_index = group;
                }
                if (local_index) {
                    *local_index = local;
                }
                if (global_index) {
                    *global_index = global;
                }
                return R6_OK;
            }
            global++;
        }
    }
    return R6_ERR_NOT_FOUND;
}
