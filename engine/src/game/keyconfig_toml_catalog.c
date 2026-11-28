/* Bounds-checked reader for the packed keyconfig line inventory. */

#include "r6/r6_keyconfig_toml_catalog.h"

#include "core/internal.h"

enum {
    R6_KEY_HEADER_SIZE = 48,
    R6_KEY_LINE_SIZE = 16,
    R6_KEY_LINES = 39,
    R6_KEY_SOURCE = 1106,
    R6_KEY_ACTIVE = 22,
    R6_KEY_COMMENTS = 13,
    R6_KEY_BLANKS = 4,
    R6_KEY_MAX_STRING = 128
};

static const unsigned char key_magic[8] = {
    'R', '6', 'K', 'E', 'Y', 0, 1, 0
};

static int key_header(const void *data, size_t size,
                      r6_keyconfig_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_keyconfig_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_KEY_HEADER_SIZE ||
            r6_memcmp(bytes, key_magic, sizeof(key_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_KEY_LINES || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_KEY_SOURCE ||
            r6_u32(bytes, 28) != R6_KEY_ACTIVE ||
            r6_u32(bytes, 32) != R6_KEY_COMMENTS ||
            r6_u32(bytes, 36) != R6_KEY_BLANKS) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.line_count = R6_KEY_LINES;
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    header.active_count = r6_u32(bytes, 28);
    header.comment_count = r6_u32(bytes, 32);
    header.blank_count = r6_u32(bytes, 36);
    header.path_offset = r6_u32(bytes, 40);
    header.path_length = r6_u32(bytes, 44);
    base = R6_KEY_HEADER_SIZE + header.line_count * R6_KEY_LINE_SIZE +
           header.string_size;
    if (base != size || header.path_length < 5) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t key_strings_base(void) {
    return R6_KEY_HEADER_SIZE + R6_KEY_LINES * R6_KEY_LINE_SIZE;
}

static int key_string(const void *data,
                      const r6_keyconfig_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = key_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_KEY_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0 ||
            (!allow_empty && !length)) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (value != 0x09u && (value < 0x20u || value > 0x7eu)) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int key_copy(const void *data,
                    const r6_keyconfig_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = key_string(data, header, offset, length, 1);
    if (result != R6_OK) {
        return result;
    }
    if (!out || !capacity || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int key_path(const void *data, size_t size, char *out,
                    size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_keyconfig_header_t header;
    int result = key_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (key_string(data, &header, header.path_offset,
                   header.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + header.path_offset + header.path_length - 5,
                      ".toml", 5) != 0) {
        return R6_ERR_FORMAT;
    }
    return key_copy(data, &header, header.path_offset, header.path_length,
                    out, capacity);
}

static int key_line(const void *data,
                    const r6_keyconfig_header_t *header,
                    uint32_t index, r6_keyconfig_line_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_keyconfig_line_t line;
    size_t at = R6_KEY_HEADER_SIZE + (size_t)index * R6_KEY_LINE_SIZE;
    if (index >= header->line_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&line, bytes + at, sizeof(line));
    if (key_string(data, header, line.text_offset, line.text_length, 1) != R6_OK ||
            line.kind > 2u || line.line != index + 1u ||
            (line.kind == 0u && line.text_length) ||
            (line.kind == 1u &&
             (line.text_length < 1 || bytes[line.text_offset] != '#')) ||
            (line.kind == 2u &&
             (!line.text_length ||
              ((bytes[line.text_offset] < 'A' ||
                bytes[line.text_offset] > 'Z') &&
               bytes[line.text_offset] != '_')))) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &line, sizeof(line));
    return R6_OK;
}

int r6_keyconfig_parse(const void *data, size_t size,
                       r6_keyconfig_header_t *out) {
    r6_keyconfig_header_t header;
    r6_keyconfig_line_t line;
    char text[R6_KEY_MAX_STRING + 1];
    uint32_t active = 0;
    uint32_t comments = 0;
    uint32_t blanks = 0;
    uint32_t at;
    int result = key_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if (key_path(data, size, text, sizeof(text)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.line_count; at++) {
        result = key_line(data, &header, at, &line);
        if (result != R6_OK) {
            return result;
        }
        active += line.kind == 2u;
        comments += line.kind == 1u;
        blanks += line.kind == 0u;
    }
    if (active != header.active_count || comments != header.comment_count ||
            blanks != header.blank_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_keyconfig_path(const void *data, size_t size, char *out,
                      size_t capacity) {
    return key_path(data, size, out, capacity);
}

int r6_keyconfig_line(const void *data, size_t size, uint32_t index,
                      r6_keyconfig_line_t *out) {
    r6_keyconfig_header_t header;
    int result = key_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return key_line(data, &header, index, out);
}

int r6_keyconfig_text(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    r6_keyconfig_header_t header;
    r6_keyconfig_line_t line;
    int result = key_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = key_line(data, &header, index, &line);
    if (result != R6_OK) {
        return result;
    }
    return key_copy(data, &header, line.text_offset, line.text_length,
                    out, capacity);
}
