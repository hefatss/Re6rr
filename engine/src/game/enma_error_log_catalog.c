/* Bounds-checked reader for packed Enma error-log layout facts. Only copied
 * paths and counts cross the bridge. */

#include "r6/r6_enma_error_log_catalog.h"

#include "core/internal.h"

enum {
    R6_ELM_HEADER_SIZE = 44,
    R6_ELM_FILE_SIZE = 36
};

static const unsigned char elm_magic[8] = {
    'R', '6', 'E', 'L', 'M', 0, 1, 0
};

static size_t elm_string_base(const r6_enma_error_log_header_t *header) {
    return R6_ELM_HEADER_SIZE + (size_t)header->file_count * R6_ELM_FILE_SIZE;
}

static int elm_header(const void *data, size_t size,
                      r6_enma_error_log_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_enma_error_log_header_t header;
    size_t files;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_ELM_HEADER_SIZE ||
            r6_memcmp(bytes, elm_magic, sizeof(elm_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.total_bytes = r6_u32(bytes, 20);
    header.total_lines = r6_u32(bytes, 24);
    header.crlf_count = r6_u32(bytes, 28);
    header.sector_lines = r6_u32(bytes, 32);
    header.vector_lines = r6_u32(bytes, 36);
    header.sector_files = r6_u32(bytes, 40);
    if (!header.file_count || !header.string_size || !header.total_lines ||
            header.sector_files > header.file_count ||
            header.sector_lines + header.vector_lines != header.total_lines ||
            header.file_count >
            ((size_t)-1 - R6_ELM_HEADER_SIZE) / R6_ELM_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_ELM_FILE_SIZE;
    base = R6_ELM_HEADER_SIZE + files;
    if (base > (size_t)-1 - header.string_size) {
        return R6_ERR_FORMAT;
    }
    if (base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int elm_validate_string(const void *data,
                               const r6_enma_error_log_header_t *header,
                               uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = elm_string_base(header);
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

static int elm_file_row(const void *data,
                        const r6_enma_error_log_header_t *header,
                        uint32_t index, r6_enma_error_log_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_enma_error_log_file_t file;
    size_t row = R6_ELM_HEADER_SIZE + (size_t)index * R6_ELM_FILE_SIZE;
    uint64_t low;
    uint64_t high;
    int result = elm_validate_string(data, header, r6_u32(bytes, row),
                                     r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(&file, bytes + row, sizeof(file));
    if (!file.lines || file.lines != file.crlf || file.shape > 1u ||
            !file.line_min || file.line_min > file.line_max || !file.tokens ||
            file.path_length < 4 ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".txt", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    low = (uint64_t)file.lines * ((uint64_t)file.line_min + 2u);
    high = (uint64_t)file.lines * ((uint64_t)file.line_max + 2u);
    if (file.size < low || file.size > high) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int elm_layout(const void *data, size_t size,
                      r6_enma_error_log_header_t *out) {
    r6_enma_error_log_header_t header;
    uint32_t bytes = 0;
    uint32_t lines = 0;
    uint32_t crlf = 0;
    uint32_t sector_lines = 0;
    uint32_t vector_lines = 0;
    uint32_t sector_files = 0;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = elm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_enma_error_log_file_t file;
        result = elm_file_row(data, &header, at, &file);
        if (result != R6_OK) {
            return result;
        }
        bytes += file.size;
        lines += file.lines;
        crlf += file.crlf;
        if (file.shape == 0) {
            sector_lines += file.lines;
            sector_files++;
        } else {
            vector_lines += file.lines;
        }
    }
    if (bytes != header.total_bytes || lines != header.total_lines ||
            crlf != header.crlf_count ||
            sector_lines != header.sector_lines ||
            vector_lines != header.vector_lines ||
            sector_files != header.sector_files) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_enma_error_log_parse(const void *data, size_t size,
                            r6_enma_error_log_header_t *out) {
    return elm_layout(data, size, out);
}

int r6_enma_error_log_file(const void *data, size_t size, uint32_t index,
                           r6_enma_error_log_file_t *out) {
    r6_enma_error_log_header_t header;
    int result = elm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return elm_file_row(data, &header, index, out);
}

int r6_enma_error_log_path(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_enma_error_log_header_t header;
    size_t row;
    int result = elm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_ELM_HEADER_SIZE + (size_t)index * R6_ELM_FILE_SIZE;
    result = elm_validate_string(data, &header, r6_u32(bytes, row),
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
