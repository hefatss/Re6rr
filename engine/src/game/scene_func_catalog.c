/* Bounds-checked reader for packed scene function inventories. */

#include "r6/r6_scene_func_catalog.h"

#include "core/internal.h"

enum {
    R6_SFN_HEADER_SIZE = 28,
    R6_SFN_FILE_SIZE = 24,
    R6_SFN_FUNC_SIZE = 16,
    R6_SFN_FILES = 3,
    R6_SFN_FUNCTIONS = 43,
    R6_SFN_SOURCE = 4289,
    R6_SFN_MAX_STRING = 128
};

static const unsigned char sfn_magic[8] = {
    'R', '6', 'S', 'F', 'N', 0, 1, 0
};

static const uint32_t sfn_counts[3] = {8, 12, 23};

static int sfn_header(const void *data, size_t size,
                      r6_scene_func_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_func_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SFN_HEADER_SIZE ||
            r6_memcmp(bytes, sfn_magic, sizeof(sfn_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_SFN_FILES ||
            r6_u32(bytes, 16) != R6_SFN_FUNCTIONS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_SFN_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.function_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_SFN_HEADER_SIZE +
           (size_t)header.file_count * R6_SFN_FILE_SIZE +
           (size_t)header.function_count * R6_SFN_FUNC_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t sfn_rows_base(void) {
    return R6_SFN_HEADER_SIZE + R6_SFN_FILES * R6_SFN_FILE_SIZE;
}

static size_t sfn_strings_base(void) {
    return sfn_rows_base() + R6_SFN_FUNCTIONS * R6_SFN_FUNC_SIZE;
}

static int sfn_string(const void *data,
                      const r6_scene_func_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = sfn_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_SFN_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0 ||
            (!allow_empty && !length)) {
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

static int sfn_copy(const void *data,
                    const r6_scene_func_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = sfn_string(data, header, offset, length, 1);
    if (result != R6_OK) {
        return result;
    }
    if (!out || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int sfn_file(const void *data, size_t size, uint32_t index,
                    r6_scene_func_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_func_header_t header;
    r6_scene_func_file_t file;
    uint32_t base = 0;
    uint32_t at;
    int result = sfn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < index; at++) {
        base += sfn_counts[at];
    }
    at = R6_SFN_HEADER_SIZE + (size_t)index * R6_SFN_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.lines || file.count != sfn_counts[index] ||
            file.function_base != base || file.path_length < 4 ||
            sfn_string(data, &header, file.path_offset,
                       file.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".Lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int sfn_row(const void *data,
                   const r6_scene_func_header_t *header,
                   uint32_t index, r6_scene_func_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_func_row_t row;
    size_t at = sfn_rows_base() + (size_t)index * R6_SFN_FUNC_SIZE;
    if (index >= header->function_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.name_length < 4 ||
            r6_memcmp(bytes + row.name_offset, "Get", 3) != 0 ||
            sfn_string(data, header, row.name_offset, row.name_length,
                       0) != R6_OK ||
            sfn_string(data, header, row.result_offset, row.result_length,
                       0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_scene_func_parse(const void *data, size_t size,
                        r6_scene_func_header_t *out) {
    r6_scene_func_header_t header;
    r6_scene_func_file_t file;
    r6_scene_func_row_t row;
    uint32_t source = 0;
    uint32_t next = 0;
    uint32_t at;
    int result = sfn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = sfn_file(data, size, at, &file);
        if (result != R6_OK || file.function_base != next) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        next += file.count;
    }
    if (source != header.source_bytes || next != header.function_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.function_count; at++) {
        result = sfn_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_scene_func_file(const void *data, size_t size, uint32_t index,
                       r6_scene_func_file_t *out) {
    return sfn_file(data, size, index, out);
}

int r6_scene_func_path(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_func_header_t header;
    r6_scene_func_file_t file;
    int result = sfn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = sfn_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return sfn_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_scene_func_row(const void *data, size_t size, uint32_t index,
                      r6_scene_func_row_t *out) {
    r6_scene_func_header_t header;
    int result = sfn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return sfn_row(data, &header, index, out);
}

int r6_scene_func_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_func_header_t header;
    r6_scene_func_row_t row;
    int result = sfn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = sfn_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return sfn_copy(data, &header, row.name_offset, row.name_length,
                    out, capacity);
}

int r6_scene_func_result(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_func_header_t header;
    r6_scene_func_row_t row;
    int result = sfn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = sfn_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return sfn_copy(data, &header, row.result_offset, row.result_length,
                    out, capacity);
}
