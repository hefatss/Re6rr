/* Bounds-checked reader for packed Strobo parameter facts. */

#include "r6/r6_strobo_parameter_catalog.h"

#include "core/internal.h"

enum {
    R6_SLO_HEADER_SIZE = 36,
    R6_SLO_FILE_SIZE = 32,
    R6_SLO_TABLE_SIZE = 16,
    R6_SLO_ROW_SIZE = 8,
    R6_SLO_SPAN_SIZE = 8,
    R6_SLO_FILES = 1,
    R6_SLO_TABLES = 2,
    R6_SLO_ROWS = 8,
    R6_SLO_FUNCTIONS = 4,
    R6_SLO_SOURCE = 3771,
    R6_SLO_LINES = 95,
    R6_SLO_MAX_STRING = 96,
    R6_SLO_MAX_VALUE = 60
};

static const unsigned char slo_magic[8] = {
    'R', '6', 'S', 'L', 'O', 0, 1, 0
};

static const char *const slo_tables[2] = {
    "StroboAeroList", "StroboRoofList"
};

static const char *const slo_functions[4] = {
    "GetStroboAeroListNumber", "GetStroboAeroList",
    "GetStroboRoofListNumber", "GetStroboRoofList"
};

static int slo_header(const void *data, size_t size,
                      r6_strobo_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_strobo_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SLO_HEADER_SIZE ||
            r6_memcmp(bytes, slo_magic, sizeof(slo_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_SLO_FILES ||
            r6_u32(bytes, 16) != R6_SLO_TABLES ||
            r6_u32(bytes, 20) != R6_SLO_ROWS ||
            r6_u32(bytes, 24) != R6_SLO_FUNCTIONS || !r6_u32(bytes, 28) ||
            r6_u32(bytes, 32) != R6_SLO_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.table_count = r6_u32(bytes, 16);
    header.row_count = r6_u32(bytes, 20);
    header.function_count = r6_u32(bytes, 24);
    header.string_size = r6_u32(bytes, 28);
    header.source_bytes = r6_u32(bytes, 32);
    base = R6_SLO_HEADER_SIZE + R6_SLO_FILES * R6_SLO_FILE_SIZE +
           R6_SLO_TABLES * R6_SLO_TABLE_SIZE +
           R6_SLO_ROWS * R6_SLO_ROW_SIZE +
           R6_SLO_FUNCTIONS * R6_SLO_SPAN_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t slo_tables_base(void) {
    return R6_SLO_HEADER_SIZE + R6_SLO_FILES * R6_SLO_FILE_SIZE;
}

static size_t slo_rows_base(void) {
    return slo_tables_base() + R6_SLO_TABLES * R6_SLO_TABLE_SIZE;
}

static size_t slo_functions_base(void) {
    return slo_rows_base() + R6_SLO_ROWS * R6_SLO_ROW_SIZE;
}

static size_t slo_strings_base(void) {
    return slo_functions_base() + R6_SLO_FUNCTIONS * R6_SLO_SPAN_SIZE;
}

static int slo_string(const void *data,
                      const r6_strobo_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = slo_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_SLO_MAX_STRING || (size_t)offset < base ||
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

static int slo_copy(const void *data,
                    const r6_strobo_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = slo_string(data, header, offset, length);
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

static int slo_file(const void *data, size_t size,
                    r6_strobo_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_strobo_header_t header;
    r6_strobo_file_t file;
    int result = slo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + R6_SLO_HEADER_SIZE, sizeof(file));
    if (file.size != R6_SLO_SOURCE || file.lines != R6_SLO_LINES ||
            file.debug || file.table_base || file.row_base != R6_SLO_ROWS ||
            file.function_base || file.path_length < 4 ||
            slo_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int slo_named(const void *data,
                     const r6_strobo_header_t *header,
                     uint32_t offset, uint32_t length,
                     const char *const *names, uint32_t count,
                     uint32_t *index_out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t index;
    if (slo_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (index = 0; index < count; index++) {
        size_t expected = r6_strlen(names[index]);
        if (length == expected &&
                r6_memcmp(bytes + offset, names[index], expected) == 0) {
            if (index_out) {
                *index_out = index;
            }
            return R6_OK;
        }
    }
    return R6_ERR_FORMAT;
}

static int slo_table(const void *data,
                     const r6_strobo_header_t *header,
                     uint32_t index, r6_strobo_table_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_strobo_table_t table;
    size_t at = slo_tables_base() + (size_t)index * R6_SLO_TABLE_SIZE;
    uint32_t matched = 0;
    if (index >= header->table_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&table, bytes + at, sizeof(table));
    if (slo_named(data, header, table.name_offset, table.name_length,
                  slo_tables, R6_SLO_TABLES, &matched) != R6_OK ||
            matched != index || table.rows != (index ? 3u : 5u) ||
            table.row_base != (index ? 5u : 0u)) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &table, sizeof(table));
    return R6_OK;
}

static int slo_row(const void *data,
                   const r6_strobo_header_t *header,
                   uint32_t index, r6_strobo_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_strobo_row_t row;
    size_t at = slo_rows_base() + (size_t)index * R6_SLO_ROW_SIZE;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.first > R6_SLO_MAX_VALUE || row.second > R6_SLO_MAX_VALUE) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int slo_function(const void *data,
                        const r6_strobo_header_t *header,
                        uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    uint32_t matched = 0;
    size_t at = slo_functions_base() + (size_t)index * R6_SLO_SPAN_SIZE;
    if (index >= header->function_count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    if (slo_named(data, header, offset, length, slo_functions,
                  R6_SLO_FUNCTIONS, &matched) != R6_OK || matched != index) {
        return R6_ERR_FORMAT;
    }
    return slo_copy(data, header, offset, length, out, capacity);
}

int r6_strobo_parse(const void *data, size_t size,
                    r6_strobo_header_t *out) {
    r6_strobo_header_t header;
    r6_strobo_file_t file;
    r6_strobo_table_t table;
    r6_strobo_row_t row;
    char text[R6_SLO_MAX_STRING + 1];
    uint32_t at;
    int result = slo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    result = slo_file(data, size, &file);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.table_count; at++) {
        result = slo_table(data, &header, at, &table);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.row_count; at++) {
        result = slo_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.function_count; at++) {
        result = slo_function(data, &header, at, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_strobo_file(const void *data, size_t size, r6_strobo_file_t *out) {
    return slo_file(data, size, out);
}

int r6_strobo_path(const void *data, size_t size, char *out,
                   size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_strobo_header_t header;
    r6_strobo_file_t file;
    int result = slo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = slo_file(data, size, &file);
    if (result != R6_OK) {
        return result;
    }
    return slo_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_strobo_table(const void *data, size_t size, uint32_t index,
                    r6_strobo_table_t *out) {
    r6_strobo_header_t header;
    int result = slo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return slo_table(data, &header, index, out);
}

int r6_strobo_table_name(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_strobo_header_t header;
    r6_strobo_table_t table;
    int result = slo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = slo_table(data, &header, index, &table);
    if (result != R6_OK) {
        return result;
    }
    return slo_copy(data, &header, table.name_offset, table.name_length,
                    out, capacity);
}

int r6_strobo_row(const void *data, size_t size, uint32_t index,
                  r6_strobo_row_t *out) {
    r6_strobo_header_t header;
    int result = slo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return slo_row(data, &header, index, out);
}

int r6_strobo_function(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    r6_strobo_header_t header;
    int result = slo_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return slo_function(data, &header, index, out, capacity);
}
