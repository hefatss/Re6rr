/* Bounds-checked reader for packed course tuning integer maps. */

#include "r6/r6_course_tuning_catalog.h"

#include "core/internal.h"

enum {
    R6_CTN_HEADER_SIZE = 32,
    R6_CTN_FILE_SIZE = 32,
    R6_CTN_RAMP_SIZE = 32,
    R6_CTN_TA_SIZE = 20,
    R6_CTN_FILES = 2,
    R6_CTN_RAMP_ROWS = 39,
    R6_CTN_TA_ROWS = 25,
    R6_CTN_SOURCE = 5267,
    R6_CTN_MAX_STRING = 96,
    R6_CTN_MAX_VALUE = 9999
};

static const unsigned char ctn_magic[8] = {
    'R', '6', 'C', 'T', 'N', 0, 1, 0
};

static int ctn_header(const void *data, size_t size,
                      r6_course_tuning_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_CTN_HEADER_SIZE ||
            r6_memcmp(bytes, ctn_magic, sizeof(ctn_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_CTN_FILES ||
            r6_u32(bytes, 16) != R6_CTN_RAMP_ROWS ||
            r6_u32(bytes, 20) != R6_CTN_TA_ROWS || !r6_u32(bytes, 24) ||
            r6_u32(bytes, 28) != R6_CTN_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.ramp_rows = r6_u32(bytes, 16);
    header.ta_rows = r6_u32(bytes, 20);
    header.string_size = r6_u32(bytes, 24);
    header.source_bytes = r6_u32(bytes, 28);
    base = R6_CTN_HEADER_SIZE +
           (size_t)header.file_count * R6_CTN_FILE_SIZE +
           (size_t)header.ramp_rows * R6_CTN_RAMP_SIZE +
           (size_t)header.ta_rows * R6_CTN_TA_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t ctn_ramp_base(void) {
    return R6_CTN_HEADER_SIZE + R6_CTN_FILES * R6_CTN_FILE_SIZE;
}

static size_t ctn_ta_base(void) {
    return ctn_ramp_base() + R6_CTN_RAMP_ROWS * R6_CTN_RAMP_SIZE;
}

static size_t ctn_strings_base(void) {
    return ctn_ta_base() + R6_CTN_TA_ROWS * R6_CTN_TA_SIZE;
}

static int ctn_string(const void *data,
                      const r6_course_tuning_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = ctn_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_CTN_MAX_STRING || (size_t)offset < base ||
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

static int ctn_copy(const void *data,
                    const r6_course_tuning_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = ctn_string(data, header, offset, length);
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

static int ctn_symbol(const void *data,
                      const r6_course_tuning_header_t *header,
                      uint32_t offset, uint32_t length,
                      const char *prefix, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t prefix_length = r6_strlen(prefix);
    if (ctn_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (!length && allow_empty) {
        return R6_OK;
    }
    if (length > prefix_length &&
            r6_memcmp(bytes + offset, prefix, prefix_length) == 0) {
        return R6_OK;
    }
    return R6_ERR_FORMAT;
}

static int ctn_file(const void *data, size_t size, uint32_t index,
                    r6_course_tuning_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_file_t file;
    size_t at;
    uint32_t expected_rows;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_CTN_HEADER_SIZE + (size_t)index * R6_CTN_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.lines || file.row_base ||
            file.path_length < 4 ||
            ctn_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    if (file.global_length == 10 &&
            r6_memcmp(bytes + file.global_offset, "RAMP_PARAM", 10) == 0) {
        expected_rows = R6_CTN_RAMP_ROWS;
    } else if (file.global_length == 8 &&
               r6_memcmp(bytes + file.global_offset, "TA_PARAM", 8) == 0) {
        expected_rows = R6_CTN_TA_ROWS;
    } else {
        return R6_ERR_FORMAT;
    }
    if (ctn_string(data, &header, file.global_offset,
                   file.global_length) != R6_OK || file.rows != expected_rows) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int ctn_ramp_row(const void *data,
                        const r6_course_tuning_header_t *header,
                        uint32_t index, r6_course_tuning_ramp_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_ramp_row_t row;
    size_t at = ctn_ramp_base() + (size_t)index * R6_CTN_RAMP_SIZE;
    if (index >= header->ramp_rows || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.normal > R6_CTN_MAX_VALUE || row.extreme > R6_CTN_MAX_VALUE ||
            ctn_symbol(data, header, row.gid_offset, row.gid_length,
                       "GID_", 0) != R6_OK ||
            ctn_symbol(data, header, row.name_offset, row.name_length,
                       "ERamp_", 0) != R6_OK ||
            ctn_symbol(data, header, row.alias_offset, row.alias_length,
                       "ERamp_", 1) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int ctn_ta_row(const void *data,
                      const r6_course_tuning_header_t *header,
                      uint32_t index, r6_course_tuning_ta_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_ta_row_t row;
    size_t at = ctn_ta_base() + (size_t)index * R6_CTN_TA_SIZE;
    int name_ok = 0;
    if (index >= header->ta_rows || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.value > R6_CTN_MAX_VALUE ||
            ctn_symbol(data, header, row.gid_offset, row.gid_length,
                       "GID_", 0) != R6_OK ||
            ctn_string(data, header, row.name_offset,
                       row.name_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (row.name_length > 10 &&
            r6_memcmp(bytes + row.name_offset, "EStage_TA_", 10) == 0) {
        name_ok = 1;
    }
    if (row.name_length > 6 &&
            r6_memcmp(bytes + row.name_offset, "ERamp_", 6) == 0) {
        name_ok = 1;
    }
    if (!row.name_length) {
        name_ok = 1;
    }
    if (!name_ok) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_course_tuning_parse(const void *data, size_t size,
                           r6_course_tuning_header_t *out) {
    r6_course_tuning_header_t header;
    r6_course_tuning_file_t file;
    r6_course_tuning_ramp_row_t ramp;
    r6_course_tuning_ta_row_t ta;
    uint32_t source = 0;
    uint32_t at;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = ctn_file(data, size, at, &file);
        if (result != R6_OK) {
            return result;
        }
        source += file.size;
    }
    if (source != header.source_bytes) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.ramp_rows; at++) {
        result = ctn_ramp_row(data, &header, at, &ramp);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.ta_rows; at++) {
        result = ctn_ta_row(data, &header, at, &ta);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_course_tuning_file(const void *data, size_t size, uint32_t index,
                          r6_course_tuning_file_t *out) {
    return ctn_file(data, size, index, out);
}

int r6_course_tuning_path(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_file_t file;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ctn_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return ctn_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_course_tuning_global(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_file_t file;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ctn_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return ctn_copy(data, &header, file.global_offset, file.global_length,
                    out, capacity);
}

int r6_course_tuning_ramp_row(const void *data, size_t size, uint32_t index,
                              r6_course_tuning_ramp_row_t *out) {
    r6_course_tuning_header_t header;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return ctn_ramp_row(data, &header, index, out);
}

int r6_course_tuning_ta_row(const void *data, size_t size, uint32_t index,
                            r6_course_tuning_ta_row_t *out) {
    r6_course_tuning_header_t header;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return ctn_ta_row(data, &header, index, out);
}

int r6_course_tuning_ramp_gid(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_ramp_row_t row;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ctn_ramp_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ctn_copy(data, &header, row.gid_offset, row.gid_length,
                    out, capacity);
}

int r6_course_tuning_ramp_name(const void *data, size_t size, uint32_t index,
                               char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_ramp_row_t row;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ctn_ramp_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ctn_copy(data, &header, row.name_offset, row.name_length,
                    out, capacity);
}

int r6_course_tuning_ramp_alias(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_ramp_row_t row;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ctn_ramp_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ctn_copy(data, &header, row.alias_offset, row.alias_length,
                    out, capacity);
}

int r6_course_tuning_ta_gid(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_ta_row_t row;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ctn_ta_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ctn_copy(data, &header, row.gid_offset, row.gid_length,
                    out, capacity);
}

int r6_course_tuning_ta_name(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_tuning_header_t header;
    r6_course_tuning_ta_row_t row;
    int result = ctn_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ctn_ta_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    return ctn_copy(data, &header, row.name_offset, row.name_length,
                    out, capacity);
}
