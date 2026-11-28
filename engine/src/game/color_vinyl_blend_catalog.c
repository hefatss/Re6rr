/* Bounds-checked reader for the packed car vinyl blend table inventory. */

#include "r6/r6_color_vinyl_blend_catalog.h"

#include "core/internal.h"

enum {
    R6_CVB_HEADER_SIZE = 44,
    R6_CVB_FILE_SIZE = 16,
    R6_CVB_ROW_SIZE = 20,
    R6_CVB_FUNC_SIZE = 12,
    R6_CVB_ROWS = 62,
    R6_CVB_TOKENS = 122,
    R6_CVB_LINES = 165,
    R6_CVB_SOURCE = 8579,
    R6_CVB_FUNCTIONS = 4,
    R6_CVB_MAX_STRING = 96
};

static const unsigned char cvb_magic[8] = {
    'R', '6', 'C', 'V', 'B', 0, 1, 0
};

static const char *const cvb_lists[4] = {
    "MiniStickerLuminosityList", "CarVinylBlendParameterDayList",
    "CarVinylBlendParameterNightList", "CarVinylBlendParameterMenuList"
};

static const char *const cvb_functions[4] = {
    "getMiniStickerLuminosity", "GetCarVinylBlendParameterDay",
    "GetCarVinylBlendParameterNight", "GetCarVinylBlendParameterMenu"
};

static const uint32_t cvb_function_lines[4] = {104u, 120u, 136u, 152u};

static size_t cvb_rows_base(void) {
    return R6_CVB_HEADER_SIZE + R6_CVB_FILE_SIZE;
}

static size_t cvb_funcs_base(void) {
    return cvb_rows_base() + R6_CVB_ROWS * R6_CVB_ROW_SIZE;
}

static size_t cvb_strings_base(void) {
    return cvb_funcs_base() + R6_CVB_FUNCTIONS * R6_CVB_FUNC_SIZE;
}

static int cvb_header(const void *data, size_t size,
                      r6_cvb_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_cvb_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_CVB_HEADER_SIZE ||
            r6_memcmp(bytes, cvb_magic, sizeof(cvb_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_CVB_ROWS ||
            r6_u32(bytes, 20) != R6_CVB_TOKENS ||
            r6_u32(bytes, 24) != R6_CVB_LINES || !r6_u32(bytes, 28) ||
            r6_u32(bytes, 32) != R6_CVB_SOURCE ||
            r6_u32(bytes, 36) != R6_CVB_FUNCTIONS ||
            r6_u32(bytes, 40) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.row_count = R6_CVB_ROWS;
    header.token_count = R6_CVB_TOKENS;
    header.line_count = R6_CVB_LINES;
    header.string_size = r6_u32(bytes, 28);
    header.source_bytes = R6_CVB_SOURCE;
    header.function_count = R6_CVB_FUNCTIONS;
    header.reserved = 0u;
    base = cvb_strings_base() + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int cvb_span(const void *data, const r6_cvb_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = cvb_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_CVB_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (digits) {
            if ((value < '0' || value > '9') && value != '.') {
                return R6_ERR_FORMAT;
            }
        } else if (value < 0x20u || value > 0x7eu) {
            return R6_ERR_FORMAT;
        }
    }
    if (!out) {
        return R6_OK;
    }
    if (!capacity || (size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static uint32_t cvb_list(uint32_t index) {
    if (index < 2u) {
        return 0u;
    }
    if (index < 22u) {
        return 1u;
    }
    return index < 42u ? 2u : 3u;
}

static uint32_t cvb_line(uint32_t index) {
    if (index < 2u) {
        return 15u + index;
    }
    if (index < 22u) {
        return 24u + index - 2u;
    }
    if (index < 42u) {
        return 51u + index - 22u;
    }
    return 78u + index - 42u;
}

static int cvb_token_span(const void *data,
                          const r6_cvb_header_t *header,
                          const r6_cvb_row_t *row, uint32_t slot,
                          uint32_t *offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t end = cvb_strings_base() + header->string_size;
    uint32_t cursor = row->token_offset;
    uint32_t at;
    uint32_t span;
    for (at = 0; at <= slot; at++) {
        if ((size_t)cursor >= end) {
            return R6_ERR_FORMAT;
        }
        span = 0;
        while ((size_t)cursor + span < end &&
               bytes[(size_t)cursor + span] != 0) {
            span++;
        }
        if ((size_t)cursor + span >= end ||
                cvb_span(data, header, cursor, span, 1, NULL, 0) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        if (at == slot) {
            *offset = cursor;
            *length = span;
            return R6_OK;
        }
        cursor += span + 1u;
    }
    return R6_ERR_FORMAT;
}

static int cvb_row(const void *data, const r6_cvb_header_t *header,
                   uint32_t index, r6_cvb_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_cvb_row_t row;
    uint32_t list;
    uint32_t slot;
    uint32_t offset;
    uint32_t length;
    char name[R6_CVB_MAX_STRING + 1];
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + cvb_rows_base() +
              (size_t)index * R6_CVB_ROW_SIZE, sizeof(row));
    if (cvb_span(data, header, row.name_offset, row.name_length, 0,
                 name, sizeof(name)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    list = cvb_list(index);
    if (row.line != cvb_line(index) ||
            row.token_count != (index < 2u ? 1u : 2u) ||
            r6_memcmp(name, cvb_lists[list], row.name_length) != 0 ||
            r6_strlen(cvb_lists[list]) != row.name_length) {
        return R6_ERR_FORMAT;
    }
    for (slot = 0; slot < row.token_count; slot++) {
        if (cvb_token_span(data, header, &row, slot,
                           &offset, &length) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int cvb_function(const void *data, const r6_cvb_header_t *header,
                        uint32_t index, r6_cvb_function_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_cvb_function_t function;
    char name[R6_CVB_MAX_STRING + 1];
    if (index >= header->function_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&function, bytes + cvb_funcs_base() +
              (size_t)index * R6_CVB_FUNC_SIZE, sizeof(function));
    if (cvb_span(data, header, function.name_offset, function.name_length,
                 0, name, sizeof(name)) != R6_OK ||
            function.line != cvb_function_lines[index] ||
            r6_strlen(cvb_functions[index]) != function.name_length ||
            r6_memcmp(name, cvb_functions[index],
                      function.name_length) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &function, sizeof(function));
    return R6_OK;
}

int r6_cvb_parse(const void *data, size_t size, r6_cvb_header_t *out) {
    r6_cvb_header_t header;
    const unsigned char *bytes = (const unsigned char *)data;
    r6_cvb_row_t row;
    r6_cvb_function_t function;
    char path[R6_CVB_MAX_STRING + 1];
    uint32_t tokens = 0;
    uint32_t at;
    int result = cvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    result = cvb_span(data, &header, r6_u32(bytes, R6_CVB_HEADER_SIZE),
                      r6_u32(bytes, R6_CVB_HEADER_SIZE +4), 0,
                      path, sizeof(path));
    if (result != R6_OK ||
            r6_u32(bytes, R6_CVB_HEADER_SIZE +4) < 5u ||
            r6_memcmp(path + r6_u32(bytes, R6_CVB_HEADER_SIZE +4) - 4,
                      ".lua", 4) != 0 ||
            r6_u32(bytes, R6_CVB_HEADER_SIZE +8) != R6_CVB_SOURCE ||
            r6_u32(bytes, R6_CVB_HEADER_SIZE +12) != R6_CVB_LINES) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.row_count; at++) {
        result = cvb_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
        tokens += row.token_count;
    }
    if (tokens != header.token_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.function_count; at++) {
        result = cvb_function(data, &header, at, &function);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_cvb_path(const void *data, size_t size, char *out, size_t capacity) {
    r6_cvb_header_t header;
    const unsigned char *bytes;
    int result = cvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    bytes = (const unsigned char *)data;
    return cvb_span(data, &header, r6_u32(bytes, R6_CVB_HEADER_SIZE),
                    r6_u32(bytes, R6_CVB_HEADER_SIZE +4), 0, out, capacity);
}

int r6_cvb_row(const void *data, size_t size, uint32_t index,
               r6_cvb_row_t *out) {
    r6_cvb_header_t header;
    int result = cvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return cvb_row(data, &header, index, out);
}

int r6_cvb_token(const void *data, size_t size, uint32_t index,
                 uint32_t slot, char *out, size_t capacity) {
    r6_cvb_header_t header;
    r6_cvb_row_t row;
    uint32_t offset;
    uint32_t length;
    int result = cvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = cvb_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot >= row.token_count) {
        return R6_ERR_ARG;
    }
    result = cvb_token_span(data, &header, &row, slot, &offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return cvb_span(data, &header, offset, length, 1, out, capacity);
}

int r6_cvb_function(const void *data, size_t size, uint32_t index,
                    r6_cvb_function_t *out) {
    r6_cvb_header_t header;
    int result = cvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return cvb_function(data, &header, index, out);
}

int r6_cvb_function_name(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    r6_cvb_header_t header;
    r6_cvb_function_t function;
    int result = cvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = cvb_function(data, &header, index, &function);
    if (result != R6_OK) {
        return result;
    }
    return cvb_span(data, &header, function.name_offset,
                    function.name_length, 0, out, capacity);
}
