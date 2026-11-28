/* Bounds-checked reader for packed WANGAN hide-clip model-name tables. */

#include "r6/r6_hide_clip_model_tables_catalog.h"

#include "core/internal.h"

enum {
    R6_HC_HEADER_SIZE = 36,
    R6_HC_FILE_SIZE = 36,
    R6_HC_SPAN_SIZE = 8,
    R6_HC_FILES = 6,
    R6_HC_NAMES = 2972,
    R6_HC_SOURCE = 140107,
    R6_HC_LINES = 2994,
    R6_HC_TABLES = 3,
    R6_HC_MAX_STRING = 96
};

static const unsigned char hc_magic[8] = {
    'R', '6', 'H', 'C', 'L', 0, 1, 0
};

static int hc_header(const void *data, size_t size,
                     r6_hide_clip_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_hide_clip_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_HC_HEADER_SIZE ||
            r6_memcmp(bytes, hc_magic, sizeof(hc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_HC_FILES ||
            r6_u32(bytes, 16) != R6_HC_NAMES || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_HC_SOURCE ||
            r6_u32(bytes, 28) != R6_HC_LINES ||
            r6_u32(bytes, 32) != R6_HC_TABLES) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.name_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    header.line_count = r6_u32(bytes, 28);
    header.table_count = r6_u32(bytes, 32);
    base = R6_HC_HEADER_SIZE +
           (size_t)header.file_count * R6_HC_FILE_SIZE +
           (size_t)header.name_count * R6_HC_SPAN_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t hc_names_base(void) {
    return R6_HC_HEADER_SIZE + R6_HC_FILES * R6_HC_FILE_SIZE;
}

static size_t hc_strings_base(void) {
    return hc_names_base() + R6_HC_NAMES * R6_HC_SPAN_SIZE;
}

static int hc_string(const void *data,
                     const r6_hide_clip_header_t *header,
                     uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = hc_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_HC_MAX_STRING || (size_t)offset < base ||
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

static int hc_copy(const void *data,
                   const r6_hide_clip_header_t *header,
                   uint32_t offset, uint32_t length,
                   char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = hc_string(data, header, offset, length);
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

static int hc_file(const void *data, size_t size, uint32_t index,
                   r6_hide_clip_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_hide_clip_header_t header;
    r6_hide_clip_file_t file;
    size_t at;
    int result = hc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_HC_HEADER_SIZE + (size_t)index * R6_HC_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.names ||
            file.lines != file.names + 3u && file.lines != file.names + 4u ||
            file.path_length < 4 ||
            hc_string(data, &header, file.path_offset,
                      file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0 ||
            file.table_length != 13u ||
            hc_string(data, &header, file.table_offset,
                      file.table_length) != R6_OK ||
            r6_memcmp(bytes + file.table_offset, "HIDE_MODEL_", 11) != 0 ||
            bytes[file.table_offset + 11] < '0' ||
            bytes[file.table_offset + 11] > '9' ||
            bytes[file.table_offset + 12] < '0' ||
            bytes[file.table_offset + 12] > '9' ||
            file.timestamp_length != 19u ||
            hc_string(data, &header, file.timestamp_offset,
                      file.timestamp_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < file.timestamp_length; at++) {
        unsigned char value = bytes[file.timestamp_offset + at];
        if (at == 4u || at == 7u) {
            if (value != '/') {
                return R6_ERR_FORMAT;
            }
        } else if (at == 10u) {
            if (value != ' ') {
                return R6_ERR_FORMAT;
            }
        } else if (at == 13u || at == 16u) {
            if (value != ':') {
                return R6_ERR_FORMAT;
            }
        } else if (value < '0' || value > '9') {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int hc_name(const void *data,
                   const r6_hide_clip_header_t *header,
                   uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    size_t at;
    if (index >= header->name_count) {
        return R6_ERR_ARG;
    }
    at = hc_names_base() + (size_t)index * R6_HC_SPAN_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    if (length < 35u || length > 64u ||
            hc_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[offset + at];
        if (!((value >= 'A' && value <= 'Z') ||
              (value >= 'a' && value <= 'z') ||
              (value >= '0' && value <= '9') || value == '_')) {
            return R6_ERR_FORMAT;
        }
    }
    return hc_copy(data, header, offset, length, out, capacity);
}

int r6_hide_clip_parse(const void *data, size_t size,
                       r6_hide_clip_header_t *out) {
    r6_hide_clip_header_t header;
    r6_hide_clip_file_t file;
    char text[R6_HC_MAX_STRING + 1];
    uint32_t names = 0;
    uint32_t lines = 0;
    uint32_t index;
    uint32_t at;
    int result = hc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < header.file_count; index++) {
        result = hc_file(data, size, index, &file);
        if (result != R6_OK ||
                file.names > header.name_count - names ||
                file.lines > header.line_count - lines) {
            return R6_ERR_FORMAT;
        }
        names += file.names;
        lines += file.lines;
    }
    if (names != header.name_count || lines != header.line_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.name_count; at++) {
        result = hc_name(data, &header, at, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_hide_clip_file(const void *data, size_t size, uint32_t index,
                      r6_hide_clip_file_t *out) {
    return hc_file(data, size, index, out);
}

int r6_hide_clip_path(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_hide_clip_header_t header;
    r6_hide_clip_file_t file;
    int result = hc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = hc_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return hc_copy(data, &header, file.path_offset, file.path_length,
                   out, capacity);
}

int r6_hide_clip_table(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_hide_clip_header_t header;
    r6_hide_clip_file_t file;
    int result = hc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = hc_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return hc_copy(data, &header, file.table_offset, file.table_length,
                   out, capacity);
}

int r6_hide_clip_timestamp(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_hide_clip_header_t header;
    r6_hide_clip_file_t file;
    int result = hc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = hc_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return hc_copy(data, &header, file.timestamp_offset,
                   file.timestamp_length, out, capacity);
}

int r6_hide_clip_name(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    r6_hide_clip_header_t header;
    int result = hc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return hc_name(data, &header, index, out, capacity);
}
