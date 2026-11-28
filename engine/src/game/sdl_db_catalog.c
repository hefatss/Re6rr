/* Bounds-checked reader for the packed SDL controller database. */

#include "r6/r6_sdl_db_catalog.h"

#include "core/internal.h"

enum {
    R6_SDL_HEADER_SIZE = 48,
    R6_SDL_LINE_SIZE = 16,
    R6_SDL_ROW_SIZE = 32,
    R6_SDL_LINES = 1916,
    R6_SDL_ROWS = 1904,
    R6_SDL_SOURCE = 506637,
    R6_SDL_COMMENTS = 7,
    R6_SDL_BLANKS = 5,
    R6_SDL_MAX_STRING = 512
};

static const unsigned char sdl_magic[8] = {
    'R', '6', 'S', 'D', 'L', 0, 1, 0
};

static const char *sdl_platforms[5] = {
    "platform:Windows", "platform:Linux", "platform:Android",
    "platform:Mac OS X", "platform:iOS"
};

static int sdl_header(const void *data, size_t size, r6_sdl_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sdl_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SDL_HEADER_SIZE ||
            r6_memcmp(bytes, sdl_magic, sizeof(sdl_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_SDL_ROWS ||
            r6_u32(bytes, 20) != R6_SDL_LINES || !r6_u32(bytes, 24) ||
            r6_u32(bytes, 28) != R6_SDL_SOURCE ||
            r6_u32(bytes, 32) != R6_SDL_COMMENTS ||
            r6_u32(bytes, 36) != R6_SDL_BLANKS) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.row_count = R6_SDL_ROWS;
    header.line_count = R6_SDL_LINES;
    header.string_size = r6_u32(bytes, 24);
    header.source_bytes = r6_u32(bytes, 28);
    header.comment_count = r6_u32(bytes, 32);
    header.blank_count = r6_u32(bytes, 36);
    header.path_offset = r6_u32(bytes, 40);
    header.path_length = r6_u32(bytes, 44);
    base = R6_SDL_HEADER_SIZE +
           (size_t)header.line_count * R6_SDL_LINE_SIZE +
           (size_t)header.row_count * R6_SDL_ROW_SIZE + header.string_size;
    if (base != size || header.path_length < 4) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t sdl_rows_base(void) {
    return R6_SDL_HEADER_SIZE + R6_SDL_LINES * R6_SDL_LINE_SIZE;
}

static size_t sdl_strings_base(void) {
    return sdl_rows_base() + R6_SDL_ROWS * R6_SDL_ROW_SIZE;
}

static int sdl_string(const void *data,
                      const r6_sdl_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = sdl_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_SDL_MAX_STRING || (size_t)offset < base ||
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

static int sdl_copy(const void *data,
                    const r6_sdl_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = sdl_string(data, header, offset, length, 1);
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

static int sdl_path(const void *data, size_t size, char *out,
                    size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sdl_header_t header;
    int result = sdl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (sdl_string(data, &header, header.path_offset,
                   header.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + header.path_offset + header.path_length - 4,
                      ".txt", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    return sdl_copy(data, &header, header.path_offset, header.path_length,
                    out, capacity);
}

static int sdl_line(const void *data,
                    const r6_sdl_header_t *header,
                    uint32_t index, r6_sdl_line_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sdl_line_t line;
    size_t at = R6_SDL_HEADER_SIZE + (size_t)index * R6_SDL_LINE_SIZE;
    if (index >= header->line_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&line, bytes + at, sizeof(line));
    if (sdl_string(data, header, line.text_offset, line.text_length, 1) != R6_OK ||
            line.kind > 2u || line.line != index + 1u ||
            (line.kind == 0u && line.text_length) ||
            (line.kind == 1u &&
             (line.text_length < 1 || bytes[line.text_offset] != '#')) ||
            (line.kind == 2u && !line.text_length)) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &line, sizeof(line));
    return R6_OK;
}

static int sdl_id(const unsigned char *bytes, uint32_t offset,
                  uint32_t length) {
    uint32_t at;
    if (length == 6u) {
        return r6_memcmp(bytes + offset, "xinput", 6) == 0 ? R6_OK :
            R6_ERR_FORMAT;
    }
    if (length != 32u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[offset + at];
        if (!((value >= '0' && value <= '9') ||
              (value >= 'a' && value <= 'f') ||
              (value >= 'A' && value <= 'F'))) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int sdl_row(const void *data,
                   const r6_sdl_header_t *header,
                   uint32_t index, r6_sdl_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sdl_row_t row;
    r6_sdl_line_t line;
    uint32_t commas = 0;
    uint32_t at;
    uint32_t platform;
    int result;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + sdl_rows_base() + (size_t)index * R6_SDL_ROW_SIZE,
              sizeof(row));
    if (!row.line || row.line > header->line_count || row.fields < 7u ||
            row.fields > 30u ||
            sdl_string(data, header, row.id_offset, row.id_length, 0) != R6_OK ||
            sdl_string(data, header, row.name_offset, row.name_length, 0) != R6_OK ||
            sdl_string(data, header, row.platform_offset,
                       row.platform_length, 0) != R6_OK ||
            sdl_id(bytes, row.id_offset, row.id_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    result = sdl_line(data, header, row.line - 1u, &line);
    if (result != R6_OK || line.kind != 2u || !line.text_length ||
            bytes[line.text_offset + line.text_length - 1u] != ',') {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < line.text_length; at++) {
        if (bytes[line.text_offset + at] == ',') {
            commas++;
        }
    }
    if (commas + 1u != row.fields) {
        return R6_ERR_FORMAT;
    }
    for (platform = 0; platform < 5; platform++) {
        size_t length = r6_strlen(sdl_platforms[platform]);
        if (row.platform_length == length &&
                r6_memcmp(bytes + row.platform_offset,
                          sdl_platforms[platform], length) == 0) {
            r6_memcpy(out, &row, sizeof(row));
            return R6_OK;
        }
    }
    return R6_ERR_FORMAT;
}

int r6_sdl_parse(const void *data, size_t size, r6_sdl_header_t *out) {
    r6_sdl_header_t header;
    r6_sdl_line_t line;
    r6_sdl_row_t row;
    char text[R6_SDL_MAX_STRING + 1];
    uint32_t blanks = 0;
    uint32_t comments = 0;
    uint32_t at;
    int result = sdl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if (sdl_path(data, size, text, sizeof(text)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.line_count; at++) {
        result = sdl_line(data, &header, at, &line);
        if (result != R6_OK) {
            return result;
        }
        blanks += line.kind == 0u;
        comments += line.kind == 1u;
    }
    if (blanks != header.blank_count || comments != header.comment_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = sdl_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_sdl_path(const void *data, size_t size, char *out, size_t capacity) {
    return sdl_path(data, size, out, capacity);
}

int r6_sdl_line(const void *data, size_t size, uint32_t index,
                r6_sdl_line_t *out) {
    r6_sdl_header_t header;
    int result = sdl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return sdl_line(data, &header, index, out);
}

int r6_sdl_line_text(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    r6_sdl_header_t header;
    r6_sdl_line_t line;
    int result = sdl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = sdl_line(data, &header, index, &line);
    if (result != R6_OK) {
        return result;
    }
    return sdl_copy(data, &header, line.text_offset, line.text_length,
                    out, capacity);
}

int r6_sdl_row(const void *data, size_t size, uint32_t index,
               r6_sdl_row_t *out) {
    r6_sdl_header_t header;
    int result = sdl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return sdl_row(data, &header, index, out);
}

int r6_sdl_field_text(const void *data, size_t size, uint32_t index,
                      uint32_t field, char *out, size_t capacity) {
    r6_sdl_header_t header;
    r6_sdl_row_t row;
    int result = sdl_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = sdl_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (field == 0u) {
        return sdl_copy(data, &header, row.id_offset, row.id_length,
                        out, capacity);
    }
    if (field == 1u) {
        return sdl_copy(data, &header, row.name_offset, row.name_length,
                        out, capacity);
    }
    if (field == 2u) {
        return sdl_copy(data, &header, row.platform_offset,
                        row.platform_length, out, capacity);
    }
    return R6_ERR_ARG;
}
