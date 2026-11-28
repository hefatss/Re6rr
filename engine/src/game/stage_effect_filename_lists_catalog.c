/* Bounds-checked reader for packed stage-effect filename lists. */

#include "r6/r6_stage_effect_filename_lists_catalog.h"

#include "core/internal.h"

enum {
    R6_SFL_HEADER_SIZE = 24,
    R6_SFL_FILE_SIZE = 16,
    R6_SFL_SPAN_SIZE = 8,
    R6_SFL_FILES = 6,
    R6_SFL_NAMES = 34,
    R6_SFL_MAX_STRING = 128
};

static const unsigned char sfl_magic[8] = {
    'R', '6', 'S', 'F', 'L', 0, 1, 0
};

static int sfl_header(const void *data, size_t size,
                      r6_stage_effect_filename_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_stage_effect_filename_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SFL_HEADER_SIZE ||
            r6_memcmp(bytes, sfl_magic, sizeof(sfl_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_SFL_FILES ||
            r6_u32(bytes, 16) != R6_SFL_NAMES || !r6_u32(bytes, 20)) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.name_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    base = R6_SFL_HEADER_SIZE +
           (size_t)header.file_count * R6_SFL_FILE_SIZE +
           (size_t)header.name_count * R6_SFL_SPAN_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t sfl_names_base(void) {
    return R6_SFL_HEADER_SIZE + R6_SFL_FILES * R6_SFL_FILE_SIZE;
}

static size_t sfl_strings_base(void) {
    return sfl_names_base() + R6_SFL_NAMES * R6_SFL_SPAN_SIZE;
}

static int sfl_string(const void *data,
                      const r6_stage_effect_filename_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = sfl_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_SFL_MAX_STRING || (size_t)offset < base ||
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

static int sfl_copy(const void *data,
                    const r6_stage_effect_filename_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = sfl_string(data, header, offset, length);
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

static int sfl_file(const void *data, size_t size, uint32_t index,
                    r6_stage_effect_filename_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_stage_effect_filename_header_t header;
    r6_stage_effect_filename_file_t file;
    size_t at;
    int result = sfl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_SFL_HEADER_SIZE + (size_t)index * R6_SFL_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.names || file.names > header.name_count ||
            file.path_length < 4 ||
            sfl_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".txt", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int sfl_name(const void *data,
                    const r6_stage_effect_filename_header_t *header,
                    uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    size_t at;
    if (index >= header->name_count) {
        return R6_ERR_ARG;
    }
    at = sfl_names_base() + (size_t)index * R6_SFL_SPAN_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    if (length < 4 ||
            sfl_string(data, header, offset, length) != R6_OK ||
            r6_memcmp(bytes + offset + length - 4, ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    return sfl_copy(data, header, offset, length, out, capacity);
}

int r6_stage_effect_filename_parse(
    const void *data, size_t size, r6_stage_effect_filename_header_t *out) {
    r6_stage_effect_filename_header_t header;
    r6_stage_effect_filename_file_t file;
    char text[R6_SFL_MAX_STRING + 1];
    uint32_t names = 0;
    uint32_t at;
    int result = sfl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = sfl_file(data, size, at, &file);
        if (result != R6_OK || file.names > header.name_count - names) {
            return R6_ERR_FORMAT;
        }
        names += file.names;
    }
    if (names != header.name_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.name_count; at++) {
        result = sfl_name(data, &header, at, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_stage_effect_filename_file(const void *data, size_t size,
                                  uint32_t index,
                                  r6_stage_effect_filename_file_t *out) {
    return sfl_file(data, size, index, out);
}

int r6_stage_effect_filename_path(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_stage_effect_filename_header_t header;
    r6_stage_effect_filename_file_t file;
    int result = sfl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = sfl_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return sfl_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_stage_effect_filename_name(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity) {
    r6_stage_effect_filename_header_t header;
    int result = sfl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return sfl_name(data, &header, index, out, capacity);
}
