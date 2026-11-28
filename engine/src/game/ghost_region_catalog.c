/* Bounds-checked reader for packed ghost-region Lua facts. Only copied paths,
 * counts and literal integers cross the bridge. */

#include "r6/r6_ghost_region_catalog.h"

#include "core/internal.h"

enum {
    R6_GRL_HEADER_SIZE = 36,
    R6_GRL_FILE_SIZE = 44
};

static const unsigned char grl_magic[8] = {
    'R', '6', 'G', 'R', 'L', 0, 1, 0
};

static size_t grl_string_base(const r6_ghost_region_header_t *header) {
    return R6_GRL_HEADER_SIZE + (size_t)header->file_count * R6_GRL_FILE_SIZE;
}

static int grl_header(const void *data, size_t size,
                      r6_ghost_region_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ghost_region_header_t header;
    size_t files;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_GRL_HEADER_SIZE ||
            r6_memcmp(bytes, grl_magic, sizeof(grl_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.source_bytes = r6_u32(bytes, 20);
    header.source_lines = r6_u32(bytes, 24);
    header.region_count = r6_u32(bytes, 28);
    header.function_count = r6_u32(bytes, 32);
    if (!header.file_count || !header.string_size || !header.source_bytes ||
            !header.source_lines || !header.region_count ||
            !header.function_count ||
            header.file_count > ((size_t)-1 - R6_GRL_HEADER_SIZE) /
                                R6_GRL_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_GRL_FILE_SIZE;
    base = R6_GRL_HEADER_SIZE + files;
    if (base > (size_t)-1 - header.string_size ||
            base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int grl_validate_string(const void *data,
                               const r6_ghost_region_header_t *header,
                               uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = grl_string_base(header);
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

static int grl_file_row(const void *data,
                        const r6_ghost_region_header_t *header, uint32_t index,
                        r6_ghost_region_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ghost_region_file_t file;
    size_t row = R6_GRL_HEADER_SIZE + (size_t)index * R6_GRL_FILE_SIZE;
    int result = grl_validate_string(data, header, r6_u32(bytes, row),
                                     r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(&file, bytes + row, sizeof(file));
    if (!file.source_size || !file.line_count || !file.region_count ||
            !file.function_count || file.region_min > file.region_max ||
            file.path_length < 4 ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int grl_layout(const void *data, size_t size,
                      r6_ghost_region_header_t *out) {
    r6_ghost_region_header_t header;
    uint32_t bytes_total = 0;
    uint32_t lines = 0;
    uint32_t regions = 0;
    uint32_t functions = 0;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = grl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_ghost_region_file_t file;
        result = grl_file_row(data, &header, at, &file);
        if (result != R6_OK) {
            return result;
        }
        bytes_total += file.source_size;
        lines += file.line_count;
        regions += file.region_count;
        functions += file.function_count;
    }
    if (bytes_total != header.source_bytes || lines != header.source_lines ||
            regions != header.region_count ||
            functions != header.function_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_ghost_region_parse(const void *data, size_t size,
                          r6_ghost_region_header_t *out) {
    return grl_layout(data, size, out);
}

int r6_ghost_region_file(const void *data, size_t size, uint32_t index,
                         r6_ghost_region_file_t *out) {
    r6_ghost_region_header_t header;
    int result = grl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return grl_file_row(data, &header, index, out);
}

int r6_ghost_region_path(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ghost_region_header_t header;
    size_t row;
    int result = grl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_GRL_HEADER_SIZE + (size_t)index * R6_GRL_FILE_SIZE;
    result = grl_validate_string(data, &header, r6_u32(bytes, row),
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
