/* Bounds-checked reader for packed NTP config line inventories. */

#include "r6/r6_ntp_config_catalog.h"

#include "core/internal.h"

enum {
    R6_NTP_HEADER_SIZE = 28,
    R6_NTP_FILE_SIZE = 20,
    R6_NTP_LINE_SIZE = 12,
    R6_NTP_FILES = 2,
    R6_NTP_LINES = 61,
    R6_NTP_SOURCE = 1425,
    R6_NTP_MAX_STRING = 128
};

static const unsigned char ntp_magic[8] = {
    'R', '6', 'N', 'T', 'P', 0, 1, 0
};

static int ntp_header(const void *data, size_t size, r6_ntp_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ntp_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_NTP_HEADER_SIZE ||
            r6_memcmp(bytes, ntp_magic, sizeof(ntp_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_NTP_FILES ||
            r6_u32(bytes, 16) != R6_NTP_LINES || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_NTP_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.line_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_NTP_HEADER_SIZE +
           (size_t)header.file_count * R6_NTP_FILE_SIZE +
           (size_t)header.line_count * R6_NTP_LINE_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t ntp_lines_base(void) {
    return R6_NTP_HEADER_SIZE + R6_NTP_FILES * R6_NTP_FILE_SIZE;
}

static size_t ntp_strings_base(void) {
    return ntp_lines_base() + R6_NTP_LINES * R6_NTP_LINE_SIZE;
}

static int ntp_string(const void *data,
                      const r6_ntp_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = ntp_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_NTP_MAX_STRING || (size_t)offset < base ||
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

static int ntp_copy(const void *data,
                    const r6_ntp_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = ntp_string(data, header, offset, length, 1);
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

static int ntp_file(const void *data, size_t size, uint32_t index,
                    r6_ntp_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ntp_header_t header;
    r6_ntp_file_t file;
    int result = ntp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + R6_NTP_HEADER_SIZE +
              (size_t)index * R6_NTP_FILE_SIZE, sizeof(file));
    if ((file.size != 713u && file.size != 712u) ||
            file.lines != (index ? 30u : 31u) ||
            file.line_base != (index ? 31u : 0u) ||
            file.path_length < 8 ||
            ntp_string(data, &header, file.path_offset,
                       file.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 5,
                      ".conf", 5) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int ntp_line(const void *data,
                    const r6_ntp_header_t *header,
                    uint32_t index, r6_ntp_line_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ntp_line_t line;
    size_t at = ntp_lines_base() + (size_t)index * R6_NTP_LINE_SIZE;
    if (index >= header->line_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&line, bytes + at, sizeof(line));
    if (ntp_string(data, header, line.text_offset, line.text_length,
                   1) != R6_OK || line.kind > 2u ||
            (line.kind == 0u && line.text_length != 0u) ||
            (line.kind == 1u &&
             bytes[line.text_offset] != '#') ||
            (line.kind == 2u &&
             bytes[line.text_offset] == '#')) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &line, sizeof(line));
    return R6_OK;
}

int r6_ntp_parse(const void *data, size_t size, r6_ntp_header_t *out) {
    r6_ntp_header_t header;
    r6_ntp_file_t file;
    r6_ntp_line_t line;
    uint32_t source = 0;
    uint32_t next = 0;
    uint32_t at;
    int result = ntp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = ntp_file(data, size, at, &file);
        if (result != R6_OK || file.line_base != next) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        next += file.lines;
    }
    if (source != header.source_bytes || next != header.line_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.line_count; at++) {
        result = ntp_line(data, &header, at, &line);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_ntp_file(const void *data, size_t size, uint32_t index,
                r6_ntp_file_t *out) {
    return ntp_file(data, size, index, out);
}

int r6_ntp_path(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ntp_header_t header;
    r6_ntp_file_t file;
    int result = ntp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ntp_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return ntp_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_ntp_line(const void *data, size_t size, uint32_t index,
                r6_ntp_line_t *out) {
    r6_ntp_header_t header;
    int result = ntp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return ntp_line(data, &header, index, out);
}

int r6_ntp_text(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ntp_header_t header;
    r6_ntp_line_t line;
    int result = ntp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ntp_line(data, &header, index, &line);
    if (result != R6_OK) {
        return result;
    }
    return ntp_copy(data, &header, line.text_offset, line.text_length,
                    out, capacity);
}
