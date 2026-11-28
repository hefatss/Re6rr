/* Bounds-checked reader for packed street-lamp table facts. Only copied
 * paths, counts and u32 flag ranges cross the bridge. */

#include "r6/r6_street_lamp_catalog.h"

#include "core/internal.h"

enum {
    R6_SLP_HEADER_SIZE = 32,
    R6_SLP_FILE_SIZE = 32,
    R6_SLP_STRIDE = 28
};

static const unsigned char slp_magic[8] = {
    'R', '6', 'S', 'L', 'P', 0, 1, 0
};

static size_t slp_string_base(const r6_street_lamp_header_t *header) {
    return R6_SLP_HEADER_SIZE + (size_t)header->file_count * R6_SLP_FILE_SIZE;
}

static int slp_header(const void *data, size_t size,
                      r6_street_lamp_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_street_lamp_header_t header;
    size_t files;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SLP_HEADER_SIZE ||
            r6_memcmp(bytes, slp_magic, sizeof(slp_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.total_bytes = r6_u32(bytes, 20);
    header.record_count = r6_u32(bytes, 24);
    header.stride = r6_u32(bytes, 28);
    if (!header.file_count || !header.string_size || !header.total_bytes ||
            !header.record_count || header.stride != R6_SLP_STRIDE ||
            header.file_count > ((size_t)-1 - R6_SLP_HEADER_SIZE) /
                                R6_SLP_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_SLP_FILE_SIZE;
    base = R6_SLP_HEADER_SIZE + files;
    if (base > (size_t)-1 - header.string_size ||
            base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int slp_validate_string(const void *data,
                               const r6_street_lamp_header_t *header,
                               uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = slp_string_base(header);
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

static int slp_file_row(const void *data,
                        const r6_street_lamp_header_t *header, uint32_t index,
                        r6_street_lamp_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_street_lamp_file_t file;
    size_t row = R6_SLP_HEADER_SIZE + (size_t)index * R6_SLP_FILE_SIZE;
    int result = slp_validate_string(data, header, r6_u32(bytes, row),
                                     r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(&file, bytes + row, sizeof(file));
    if (!file.record_count || file.stride != R6_SLP_STRIDE ||
            file.record_count > header->record_count ||
            file.size != file.record_count * R6_SLP_STRIDE ||
            file.flag_min > file.flag_max || !file.distinct ||
            file.distinct > file.record_count || file.path_length < 4 ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".bin", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int slp_layout(const void *data, size_t size,
                      r6_street_lamp_header_t *out) {
    r6_street_lamp_header_t header;
    uint32_t total_bytes = 0;
    uint32_t records = 0;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = slp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_street_lamp_file_t file;
        result = slp_file_row(data, &header, at, &file);
        if (result != R6_OK || records > header.record_count -
                file.record_count) {
            return R6_ERR_FORMAT;
        }
        records += file.record_count;
        total_bytes += file.size;
    }
    if (records != header.record_count || total_bytes != header.total_bytes) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_street_lamp_parse(const void *data, size_t size,
                         r6_street_lamp_header_t *out) {
    return slp_layout(data, size, out);
}

int r6_street_lamp_file(const void *data, size_t size, uint32_t index,
                        r6_street_lamp_file_t *out) {
    r6_street_lamp_header_t header;
    int result = slp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return slp_file_row(data, &header, index, out);
}

int r6_street_lamp_path(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_street_lamp_header_t header;
    size_t row;
    int result = slp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_SLP_HEADER_SIZE + (size_t)index * R6_SLP_FILE_SIZE;
    result = slp_validate_string(data, &header, r6_u32(bytes, row),
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
