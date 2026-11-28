/* Bounds-checked reader for the packed AMCUS INI key inventory. */

#include "r6/r6_amcus_ini_keys_catalog.h"

#include "core/internal.h"

enum {
    R6_AIK_HEADER_SIZE = 48,
    R6_AIK_FILE_SIZE = 20,
    R6_AIK_LINE_SIZE = 24,
    R6_AIK_FILES = 3,
    R6_AIK_LINES = 204,
    R6_AIK_SOURCE = 5139,
    R6_AIK_SECTIONS = 22,
    R6_AIK_KEYS = 139,
    R6_AIK_COMMENTS = 23,
    R6_AIK_BLANKS = 20,
    R6_AIK_MAX_STRING = 96
};

static const unsigned char aik_magic[8] = {
    'R', '6', 'A', 'I', 'K', 0, 1, 0
};

static const uint32_t aik_sizes[3] = {2426u, 2518u, 195u};
static const uint32_t aik_lines[3] = {96u, 98u, 10u};
static const uint32_t aik_bases[3] = {0u, 96u, 194u};

static int aik_header(const void *data, size_t size,
                      r6_amcus_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_amcus_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_AIK_HEADER_SIZE ||
            r6_memcmp(bytes, aik_magic, sizeof(aik_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_AIK_FILES ||
            r6_u32(bytes, 16) != R6_AIK_LINES || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_AIK_SOURCE ||
            r6_u32(bytes, 28) != R6_AIK_SECTIONS ||
            r6_u32(bytes, 32) != R6_AIK_KEYS ||
            r6_u32(bytes, 36) != R6_AIK_COMMENTS ||
            r6_u32(bytes, 40) != R6_AIK_BLANKS ||
            r6_u32(bytes, 44) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_AIK_FILES;
    header.line_count = R6_AIK_LINES;
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = R6_AIK_SOURCE;
    header.section_count = R6_AIK_SECTIONS;
    header.key_count = R6_AIK_KEYS;
    header.comment_count = R6_AIK_COMMENTS;
    header.blank_count = R6_AIK_BLANKS;
    header.reserved = 0u;
    base = R6_AIK_HEADER_SIZE +
           (size_t)header.file_count * R6_AIK_FILE_SIZE +
           (size_t)header.line_count * R6_AIK_LINE_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t aik_lines_base(void) {
    return R6_AIK_HEADER_SIZE + R6_AIK_FILES * R6_AIK_FILE_SIZE;
}

static size_t aik_strings_base(void) {
    return aik_lines_base() + R6_AIK_LINES * R6_AIK_LINE_SIZE;
}

static int aik_string(const void *data,
                      const r6_amcus_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = aik_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (length > R6_AIK_MAX_STRING || (size_t)offset < base ||
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

static int aik_copy(const void *data,
                    const r6_amcus_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = aik_string(data, header, offset, length, 1);
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

static int aik_file(const void *data, size_t size, uint32_t index,
                    r6_amcus_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_amcus_header_t header;
    r6_amcus_file_t file;
    int result = aik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + R6_AIK_HEADER_SIZE +
              (size_t)index * R6_AIK_FILE_SIZE, sizeof(file));
    if (file.size != aik_sizes[index] || file.lines != aik_lines[index] ||
            file.line_base != aik_bases[index] || file.path_length < 9 ||
            aik_string(data, &header, file.path_offset,
                       file.path_length, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                  ".ini", 4) != 0 &&
            (file.path_length < 9 ||
             r6_memcmp(bytes + file.path_offset + file.path_length - 9,
                       ".ini.orig", 9) != 0)) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int aik_line(const void *data,
                    const r6_amcus_header_t *header,
                    uint32_t index, r6_amcus_line_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_amcus_line_t line;
    uint32_t at;
    if (index >= header->line_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&line, bytes + aik_lines_base() +
              (size_t)index * R6_AIK_LINE_SIZE, sizeof(line));
    if (aik_string(data, header, line.name_offset, line.name_length, 1) != R6_OK ||
            line.kind > 3u || line.line != index + 1u ||
            line.value_present > 1u || line.section > R6_AIK_SECTIONS) {
        return R6_ERR_FORMAT;
    }
    if (line.kind < 2u) {
        if (line.name_length || line.value_present) {
            return R6_ERR_FORMAT;
        }
    } else {
        if (!line.name_length || (line.kind == 2u && line.value_present)) {
            return R6_ERR_FORMAT;
        }
        for (at = 0; at < line.name_length; at++) {
            unsigned char value = bytes[line.name_offset + at];
            if (value == '=' || value == '[' || value == ']') {
                return R6_ERR_FORMAT;
            }
        }
    }
    r6_memcpy(out, &line, sizeof(line));
    return R6_OK;
}

int r6_amcus_parse(const void *data, size_t size, r6_amcus_header_t *out) {
    r6_amcus_header_t header;
    r6_amcus_file_t file;
    r6_amcus_line_t line;
    char text[R6_AIK_MAX_STRING + 1];
    uint32_t source = 0;
    uint32_t next = 0;
    uint32_t sections = 0;
    uint32_t keys = 0;
    uint32_t comments = 0;
    uint32_t blanks = 0;
    uint32_t at;
    int result = aik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = aik_file(data, size, at, &file);
        if (result != R6_OK || file.line_base != next) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        next += file.lines;
    }
    if (source != header.source_bytes || next != header.line_count ||
            aik_file(data, size, 0, &file) != R6_OK ||
            aik_copy(data, &header, file.path_offset, file.path_length,
                     text, sizeof(text)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.line_count; at++) {
        result = aik_line(data, &header, at, &line);
        if (result != R6_OK) {
            return result;
        }
        sections += line.kind == 2u;
        keys += line.kind == 3u;
        comments += line.kind == 1u;
        blanks += line.kind == 0u;
    }
    if (sections != header.section_count || keys != header.key_count ||
            comments != header.comment_count || blanks != header.blank_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_amcus_file(const void *data, size_t size, uint32_t index,
                  r6_amcus_file_t *out) {
    return aik_file(data, size, index, out);
}

int r6_amcus_path(const void *data, size_t size, uint32_t index,
                  char *out, size_t capacity) {
    r6_amcus_header_t header;
    r6_amcus_file_t file;
    int result = aik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = aik_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return aik_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_amcus_line(const void *data, size_t size, uint32_t index,
                  r6_amcus_line_t *out) {
    r6_amcus_header_t header;
    int result = aik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return aik_line(data, &header, index, out);
}

int r6_amcus_name(const void *data, size_t size, uint32_t index,
                  char *out, size_t capacity) {
    r6_amcus_header_t header;
    r6_amcus_line_t line;
    int result = aik_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = aik_line(data, &header, index, &line);
    if (result != R6_OK) {
        return result;
    }
    return aik_copy(data, &header, line.name_offset, line.name_length,
                    out, capacity);
}
