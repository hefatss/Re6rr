/* Bounds-checked reader for packed carryover token inventories. */

#include "r6/r6_carryover_catalog.h"

#include "core/internal.h"

enum {
    R6_CRY_HEADER_SIZE = 32,
    R6_CRY_RECORD_SIZE = 16,
    R6_CRY_ROW_SIZE = 60,
    R6_CRY_RECORDS = 7,
    R6_CRY_ROWS = 4,
    R6_CRY_SOURCE = 398,
    R6_CRY_MAX_STRING = 64,
    R6_CRY_FIELDS = 7
};

static const unsigned char cry_magic[8] = {
    'R', '6', 'C', 'R', 'Y', 0, 1, 0
};

static int cry_header(const void *data, size_t size,
                      r6_carryover_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_carryover_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_CRY_HEADER_SIZE ||
            r6_memcmp(bytes, cry_magic, sizeof(cry_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != 1u ||
            r6_u32(bytes, 16) != R6_CRY_RECORDS ||
            r6_u32(bytes, 20) != R6_CRY_ROWS || !r6_u32(bytes, 24) ||
            r6_u32(bytes, 28) != R6_CRY_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = 1u;
    header.record_count = r6_u32(bytes, 16);
    header.row_count = r6_u32(bytes, 20);
    header.string_size = r6_u32(bytes, 24);
    header.source_bytes = r6_u32(bytes, 28);
    base = R6_CRY_HEADER_SIZE +
           (size_t)header.record_count * R6_CRY_RECORD_SIZE +
           (size_t)header.row_count * R6_CRY_ROW_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t cry_rows_base(void) {
    return R6_CRY_HEADER_SIZE + R6_CRY_RECORDS * R6_CRY_RECORD_SIZE;
}

static size_t cry_strings_base(void) {
    return cry_rows_base() + R6_CRY_ROWS * R6_CRY_ROW_SIZE;
}

static int cry_string(const void *data,
                      const r6_carryover_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = cry_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_CRY_MAX_STRING || (size_t)offset < base ||
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

static int cry_number(const void *data,
                      const r6_carryover_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t at;
    int digits = 0;
    int result = cry_string(data, header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (value >= '0' && value <= '9') {
            digits++;
        } else if (value != '.' && value != '-' && value != '+') {
            return R6_ERR_FORMAT;
        }
    }
    return digits ? R6_OK : R6_ERR_FORMAT;
}

static int cry_copy(const void *data,
                    const r6_carryover_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = cry_string(data, header, offset, length);
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

static int cry_record(const void *data, size_t size, uint32_t index,
                      r6_carryover_record_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_carryover_header_t header;
    r6_carryover_record_t record;
    size_t at = R6_CRY_HEADER_SIZE + (size_t)index * R6_CRY_RECORD_SIZE;
    int result = cry_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.record_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&record, bytes + at, sizeof(record));
    if (cry_string(data, &header, record.text_offset,
                   record.text_length) != R6_OK ||
            record.line != (index ? index : 0u)) {
        /* line 0 is the source path; token lines are 1..6. */
        return R6_ERR_FORMAT;
    }
    if (index == 0u) {
        if (record.kind != 2u || record.text_length < 4 ||
                r6_memcmp(bytes + record.text_offset +
                          record.text_length - 4, ".txt", 4) != 0) {
            return R6_ERR_FORMAT;
        }
    } else if (index == 1u) {
        if (record.kind != 0u || record.text_length < 6 ||
                r6_memcmp(bytes + record.text_offset, "Series", 6) != 0) {
            return R6_ERR_FORMAT;
        }
    } else if (record.kind != 1u ||
               cry_number(data, &header, record.text_offset,
                          record.text_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &record, sizeof(record));
    return R6_OK;
}

static int cry_row(const void *data,
                   const r6_carryover_header_t *header,
                   uint32_t index, r6_carryover_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_carryover_row_t row;
    const uint32_t *spans = (const uint32_t *)&row;
    size_t at = cry_rows_base() + (size_t)index * R6_CRY_ROW_SIZE;
    uint32_t field;
    if (index >= header->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.line != index + 7u ||
            cry_number(data, header, spans[2], spans[3]) != R6_OK ||
            cry_number(data, header, spans[6], spans[7]) != R6_OK ||
            cry_number(data, header, spans[8], spans[9]) != R6_OK ||
            cry_number(data, header, spans[10], spans[11]) != R6_OK ||
            cry_number(data, header, spans[12], spans[13]) != R6_OK ||
            cry_string(data, header, spans[4], spans[5]) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (!((spans[1] == 4 &&
           r6_memcmp(bytes + spans[0], "true", 4) == 0) ||
          (spans[1] == 5 &&
           r6_memcmp(bytes + spans[0], "false", 5) == 0))) {
        return R6_ERR_FORMAT;
    }
    for (field = 0; field < spans[5]; field++) {
        unsigned char value = bytes[spans[4] + field];
        if (!((value >= 'A' && value <= 'Z') ||
              (value >= 'a' && value <= 'z') ||
              (value >= '0' && value <= '9') || value == '_')) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

int r6_carryover_parse(const void *data, size_t size,
                       r6_carryover_header_t *out) {
    r6_carryover_header_t header;
    r6_carryover_record_t record;
    r6_carryover_row_t row;
    uint32_t at;
    int result = cry_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.record_count; at++) {
        result = cry_record(data, size, at, &record);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.row_count; at++) {
        result = cry_row(data, &header, at, &row);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_carryover_record(const void *data, size_t size, uint32_t index,
                        r6_carryover_record_t *out) {
    return cry_record(data, size, index, out);
}

int r6_carryover_text(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    r6_carryover_header_t header;
    r6_carryover_record_t record;
    int result = cry_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = cry_record(data, size, index, &record);
    if (result != R6_OK) {
        return result;
    }
    return cry_copy(data, &header, record.text_offset, record.text_length,
                    out, capacity);
}

int r6_carryover_row(const void *data, size_t size, uint32_t index,
                     r6_carryover_row_t *out) {
    r6_carryover_header_t header;
    int result = cry_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return cry_row(data, &header, index, out);
}

int r6_carryover_field(const void *data, size_t size, uint32_t index,
                       uint32_t field, char *out, size_t capacity) {
    r6_carryover_header_t header;
    r6_carryover_row_t row;
    const uint32_t *spans;
    int result = cry_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = cry_row(data, &header, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (field >= R6_CRY_FIELDS) {
        return R6_ERR_ARG;
    }
    spans = (const uint32_t *)&row;
    return cry_copy(data, &header, spans[field * 2], spans[field * 2 + 1],
                    out, capacity);
}
