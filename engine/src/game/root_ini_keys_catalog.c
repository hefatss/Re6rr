/* Bounds-checked reader for packed root INI section/key inventories. */

#include "r6/r6_root_ini_keys_catalog.h"

#include "core/internal.h"

enum {
    R6_RIK_HEADER_SIZE = 28,
    R6_RIK_FILE_SIZE = 20,
    R6_RIK_LINE_SIZE = 24,
    R6_RIK_FILES = 2,
    R6_RIK_LINES = 39,
    R6_RIK_SOURCE = 778,
    R6_RIK_SECTIONS = 8,
    R6_RIK_KEYS = 31,
    R6_RIK_MAX_STRING = 96
};

static const unsigned char rik_magic[8] = {
    'R', '6', 'R', 'I', 'K', 0, 1, 0
};

static const uint32_t rik_sizes[2] = {63u, 715u};
static const uint32_t rik_lines[2] = {3u, 36u};
static const uint32_t rik_bases[2] = {0u, 3u};

static int rik_header(const void *data, size_t size,
                      r6_ini_keys_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ini_keys_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_RIK_HEADER_SIZE ||
            r6_memcmp(bytes, rik_magic, sizeof(rik_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_RIK_FILES ||
            r6_u32(bytes, 16) != R6_RIK_LINES || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_RIK_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.line_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_RIK_HEADER_SIZE +
           (size_t)header.file_count * R6_RIK_FILE_SIZE +
           (size_t)header.line_count * R6_RIK_LINE_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t rik_lines_base(void) {
    return R6_RIK_HEADER_SIZE + R6_RIK_FILES * R6_RIK_FILE_SIZE;
}

static size_t rik_strings_base(void) {
    return rik_lines_base() + R6_RIK_LINES * R6_RIK_LINE_SIZE;
}

static int rik_string(const void *data,
                      const r6_ini_keys_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = rik_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_RIK_MAX_STRING || (size_t)offset < base ||
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

static int rik_copy(const void *data,
                    const r6_ini_keys_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = rik_string(data, header, offset, length, 1);
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

static int rik_file(const void *data, size_t size, uint32_t index,
                    r6_ini_keys_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ini_keys_header_t header;
    r6_ini_keys_file_t file;
    int result = rik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + R6_RIK_HEADER_SIZE +
              (size_t)index * R6_RIK_FILE_SIZE, sizeof(file));
    if (file.size != rik_sizes[index] || file.lines != rik_lines[index] ||
            file.line_base != rik_bases[index] || file.path_length < 4 ||
            rik_string(data, &header, file.path_offset,
                       file.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".ini", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int rik_line(const void *data,
                    const r6_ini_keys_header_t *header,
                    uint32_t index, r6_ini_keys_line_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ini_keys_line_t line;
    uint32_t at = rik_lines_base() + (size_t)index * R6_RIK_LINE_SIZE;
    if (index >= header->line_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&line, bytes + at, sizeof(line));
    if (rik_string(data, header, line.name_offset, line.name_length, 1) != R6_OK ||
            line.kind > 2u || line.line != index + 1u ||
            line.value_present > 1u || line.section > R6_RIK_SECTIONS) {
        return R6_ERR_FORMAT;
    }
    if (line.kind == 0u) {
        if (line.name_length || line.value_present || line.section) {
            return R6_ERR_FORMAT;
        }
    } else {
        if (!line.name_length) {
            return R6_ERR_FORMAT;
        }
        for (at = 0; at < line.name_length; at++) {
            unsigned char value = bytes[line.name_offset + at];
            if (line.kind == 2u && value == '=') {
                return R6_ERR_FORMAT;
            }
        }
    }
    r6_memcpy(out, &line, sizeof(line));
    return R6_OK;
}

int r6_ini_keys_parse(const void *data, size_t size,
                      r6_ini_keys_header_t *out) {
    r6_ini_keys_header_t header;
    r6_ini_keys_file_t file;
    r6_ini_keys_line_t line;
    char text[R6_RIK_MAX_STRING + 1];
    uint32_t source = 0;
    uint32_t next = 0;
    uint32_t sections = 0;
    uint32_t keys = 0;
    uint32_t at;
    int result = rik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = rik_file(data, size, at, &file);
        if (result != R6_OK || file.line_base != next) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        next += file.lines;
    }
    if (source != header.source_bytes || next != header.line_count) {
        return R6_ERR_FORMAT;
    }
    if (rik_file(data, size, 0, &file) != R6_OK ||
            rik_copy(data, &header, file.path_offset, file.path_length,
                     text, sizeof(text)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.line_count; at++) {
        result = rik_line(data, &header, at, &line);
        if (result != R6_OK) {
            return result;
        }
        sections += line.kind == 1u;
        keys += line.kind == 2u;
    }
    if (sections != R6_RIK_SECTIONS || keys != R6_RIK_KEYS) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_ini_keys_file(const void *data, size_t size, uint32_t index,
                     r6_ini_keys_file_t *out) {
    return rik_file(data, size, index, out);
}

int r6_ini_keys_path(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    r6_ini_keys_header_t header;
    r6_ini_keys_file_t file;
    int result = rik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = rik_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return rik_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_ini_keys_line(const void *data, size_t size, uint32_t index,
                     r6_ini_keys_line_t *out) {
    r6_ini_keys_header_t header;
    int result = rik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return rik_line(data, &header, index, out);
}

int r6_ini_keys_name(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    r6_ini_keys_header_t header;
    r6_ini_keys_line_t line;
    int result = rik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = rik_line(data, &header, index, &line);
    if (result != R6_OK) {
        return result;
    }
    return rik_copy(data, &header, line.name_offset, line.name_length,
                    out, capacity);
}
