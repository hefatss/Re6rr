/* Bounds-checked reader for packed default ghost table layout facts. Only
 * copied paths, counts, code words and name-length ranges cross the bridge. */

#include "r6/r6_default_ghost_catalog.h"

#include "core/internal.h"

enum {
    R6_GH_HEADER_SIZE = 52,
    R6_GH_FILE_SIZE = 44,
    R6_GH_STRIDE = 136,
    R6_GH_NAME1_OFFSET = 0x08,
    R6_GH_NAME1_CAPACITY = 16,
    R6_GH_NAME2_OFFSET = 0x60,
    R6_GH_NAME2_CAPACITY = 28,
    R6_GH_TUPLE_A_OFFSET = 0x54,
    R6_GH_TUPLE_B_OFFSET = 0x80
};

static const unsigned char gh_magic[8] = {
    'R', '6', 'G', 'H', 0, 1, 0, 0
};

static size_t gh_string_base(const r6_default_ghost_header_t *header) {
    return R6_GH_HEADER_SIZE + (size_t)header->file_count * R6_GH_FILE_SIZE;
}

static int gh_header(const void *data, size_t size,
                     r6_default_ghost_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_default_ghost_header_t header;
    size_t files;
    size_t base;
    size_t end;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_GH_HEADER_SIZE ||
            r6_memcmp(bytes, gh_magic, sizeof(gh_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.stride = r6_u32(bytes, 20);
    header.name1_offset = r6_u32(bytes, 24);
    header.name1_capacity = r6_u32(bytes, 28);
    header.name2_offset = r6_u32(bytes, 32);
    header.name2_capacity = r6_u32(bytes, 36);
    header.tuple_a_offset = r6_u32(bytes, 40);
    header.tuple_b_offset = r6_u32(bytes, 44);
    header.record_count = r6_u32(bytes, 48);
    if (!header.file_count || !header.string_size || !header.record_count ||
            header.stride != R6_GH_STRIDE ||
            header.name1_offset != R6_GH_NAME1_OFFSET ||
            header.name1_capacity != R6_GH_NAME1_CAPACITY ||
            header.name2_offset != R6_GH_NAME2_OFFSET ||
            header.name2_capacity != R6_GH_NAME2_CAPACITY ||
            header.tuple_a_offset != R6_GH_TUPLE_A_OFFSET ||
            header.tuple_b_offset != R6_GH_TUPLE_B_OFFSET ||
            header.file_count > ((size_t)-1 - R6_GH_HEADER_SIZE) /
                                R6_GH_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_GH_FILE_SIZE;
    base = R6_GH_HEADER_SIZE + files;
    if (base > (size_t)-1 - header.string_size) {
        return R6_ERR_FORMAT;
    }
    end = base + header.string_size;
    if (end != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int gh_validate_string(const void *data,
                              const r6_default_ghost_header_t *header,
                              uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = gh_string_base(header);
    size_t end = base + header->string_size;
    size_t at;
    if (!length || (size_t)offset < base || (size_t)offset >= end ||
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

static int gh_file_row(const void *data,
                       const r6_default_ghost_header_t *header,
                       uint32_t index, r6_default_ghost_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_default_ghost_file_t file;
    size_t row = R6_GH_HEADER_SIZE + (size_t)index * R6_GH_FILE_SIZE;
    int result = gh_validate_string(data, header, r6_u32(bytes, row),
                                    r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(&file, bytes + row, sizeof(file));
    if (!file.record_count || !file.code ||
            (size_t)file.record_count * R6_GH_STRIDE != file.file_size ||
            !file.name1_min || file.name1_min > file.name1_max ||
            file.name1_max >= R6_GH_NAME1_CAPACITY ||
            !file.name2_min || file.name2_min > file.name2_max ||
            file.name2_max >= R6_GH_NAME2_CAPACITY ||
            !file.tuple_a_count || file.tuple_a_count > file.record_count ||
            !file.tuple_b_count || file.tuple_b_count > file.record_count ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".bin", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int gh_layout(const void *data, size_t size,
                     r6_default_ghost_header_t *out) {
    r6_default_ghost_header_t header;
    uint32_t records = 0;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = gh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_default_ghost_file_t file;
        result = gh_file_row(data, &header, at, &file);
        if (result != R6_OK || records > header.record_count - file.record_count) {
            return R6_ERR_FORMAT;
        }
        records += file.record_count;
    }
    if (records != header.record_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_default_ghost_parse(const void *data, size_t size,
                           r6_default_ghost_header_t *out) {
    return gh_layout(data, size, out);
}

int r6_default_ghost_file(const void *data, size_t size, uint32_t index,
                          r6_default_ghost_file_t *out) {
    r6_default_ghost_header_t header;
    int result = gh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return gh_file_row(data, &header, index, out);
}

int r6_default_ghost_path(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_default_ghost_header_t header;
    size_t row;
    int result = gh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_GH_HEADER_SIZE + (size_t)index * R6_GH_FILE_SIZE;
    result = gh_validate_string(data, &header, r6_u32(bytes, row),
                                r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)r6_u32(bytes, row + 4) + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + r6_u32(bytes, row), r6_u32(bytes, row + 4));
    out[r6_u32(bytes, row + 4)] = 0;
    return R6_OK;
}
