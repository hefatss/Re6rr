/* Bounds-checked reader for the packed tire/lamp/strobo position inventory. */

#include "r6/r6_tire_lamp_pos_catalog.h"

#include "core/internal.h"

enum {
    R6_TLP_HEADER_SIZE = 52,
    R6_TLP_FILE_SIZE = 32,
    R6_TLP_SECTION_SIZE = 32,
    R6_TLP_ROW_SIZE = 16,
    R6_TLP_FILES = 255,
    R6_TLP_SECTIONS = 28797,
    R6_TLP_LISTS = 14775,
    R6_TLP_SCALARS = 14022,
    R6_TLP_ROWS = 23759,
    R6_TLP_TOKENS = 71277,
    R6_TLP_LINES = 681731,
    R6_TLP_SOURCE = 22041850,
    R6_TLP_MAX_STRING = 96
};

static const unsigned char tlp_magic[8] = {
    'R', '6', 'T', 'L', 'P', 0, 1, 0
};

static size_t tlp_files_base(void) {
    return R6_TLP_HEADER_SIZE;
}

static size_t tlp_sections_base(void) {
    return tlp_files_base() + R6_TLP_FILES * R6_TLP_FILE_SIZE;
}

static size_t tlp_rows_base(void) {
    return tlp_sections_base() + R6_TLP_SECTIONS * R6_TLP_SECTION_SIZE;
}

static size_t tlp_strings_base(void) {
    return tlp_rows_base() + R6_TLP_ROWS * R6_TLP_ROW_SIZE;
}

static int tlp_header(const void *data, size_t size, r6_tlp_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tlp_header_t header;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_TLP_HEADER_SIZE ||
            r6_memcmp(bytes, tlp_magic, sizeof(tlp_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_TLP_FILES ||
            r6_u32(bytes, 16) != R6_TLP_SECTIONS ||
            r6_u32(bytes, 20) != R6_TLP_LISTS ||
            r6_u32(bytes, 24) != R6_TLP_SCALARS ||
            r6_u32(bytes, 28) != R6_TLP_ROWS ||
            r6_u32(bytes, 32) != R6_TLP_TOKENS ||
            r6_u32(bytes, 36) != R6_TLP_LINES ||
            r6_u32(bytes, 40) != R6_TLP_SOURCE || !r6_u32(bytes, 44) ||
            r6_u32(bytes, 48) != 0u ||
            tlp_strings_base() + r6_u32(bytes, 44) != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_TLP_FILES;
    header.section_count = R6_TLP_SECTIONS;
    header.list_count = R6_TLP_LISTS;
    header.scalar_count = R6_TLP_SCALARS;
    header.row_count = R6_TLP_ROWS;
    header.token_count = R6_TLP_TOKENS;
    header.line_count = R6_TLP_LINES;
    header.source_bytes = R6_TLP_SOURCE;
    header.string_size = r6_u32(bytes, 44);
    header.reserved = 0u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int tlp_span(const void *data, const r6_tlp_header_t *header,
                    uint32_t offset, uint32_t length, int digits,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = tlp_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_TLP_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (digits) {
            if ((value < '0' || value > '9') && value != '.' &&
                    (at != 0u || value != '-')) {
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

static int tlp_token_length(const void *data,
                            const r6_tlp_header_t *header,
                            uint32_t offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t end = tlp_strings_base() + header->string_size;
    uint32_t span = 0;
    if ((size_t)offset < tlp_strings_base() || (size_t)offset >= end) {
        return R6_ERR_FORMAT;
    }
    while ((size_t)offset + span < end &&
           bytes[(size_t)offset + span] != 0) {
        span++;
    }
    if ((size_t)offset + span >= end ||
            tlp_span(data, header, offset, span, 1, NULL, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    *length = span;
    return R6_OK;
}

static int tlp_file_at(const void *data, size_t size,
                       const r6_tlp_header_t *header, uint32_t index,
                       r6_tlp_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tlp_file_t file;
    char name[R6_TLP_MAX_STRING + 1];
    char car[R6_TLP_MAX_STRING + 1];
    uint32_t at;
    int result;
    if (index >= header->file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + tlp_files_base() +
              (size_t)index * R6_TLP_FILE_SIZE, sizeof(file));
    result = tlp_span(data, header, file.name_offset, file.name_length,
                      0, name, sizeof(name));
    if (result != R6_OK) {
        return result;
    }
    result = tlp_span(data, header, file.car_id_offset, file.car_id_length,
                      0, car, sizeof(car));
    if (result != R6_OK) {
        return result;
    }
    if (file.name_length < 16u ||
            r6_memcmp(name, "getTirePos_", 11) != 0 ||
            r6_memcmp(name + file.name_length - 4, ".lua", 4) != 0 ||
            !file.car_id_length || !file.size || !file.lines ||
            !file.section_count || file.section_base >= header->section_count ||
            file.section_count > header->section_count - file.section_base) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < file.car_id_length; at++) {
        unsigned char value = (unsigned char)car[at];
        if ((value < 'A' || value > 'Z') && (value < 'a' || value > 'z') &&
            (value < '0' || value > '9') && value != '_') {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int tlp_has_num(const char *key, uint32_t length) {
    uint32_t at;
    for (at = 0; at + 3u < length; at++) {
        if (r6_memcmp(key + at, "Num", 3) == 0) {
            return 1;
        }
    }
    return 0;
}

static int tlp_section_at(const void *data, size_t size,
                          const r6_tlp_header_t *header, uint32_t index,
                          r6_tlp_section_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tlp_section_t section;
    char key[R6_TLP_MAX_STRING + 1];
    int result;
    if (index >= header->section_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&section, bytes + tlp_sections_base() +
              (size_t)index * R6_TLP_SECTION_SIZE, sizeof(section));
    result = tlp_span(data, header, section.key_offset, section.key_length,
                      0, key, sizeof(key));
    if (result != R6_OK) {
        return result;
    }
    if (!section.line || section.row_base > header->row_count ||
            section.kind > 1u) {
        return R6_ERR_FORMAT;
    }
    if (section.kind == 0u) {
        if (tlp_has_num(key, section.key_length) || section.value_offset ||
                section.value_length ||
                section.row_count > header->row_count - section.row_base) {
            return R6_ERR_FORMAT;
        }
    } else {
        if (!tlp_has_num(key, section.key_length) || !section.value_length ||
                section.row_count ||
                tlp_span(data, header, section.value_offset,
                         section.value_length, 1, NULL, 0) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &section, sizeof(section));
    return R6_OK;
}

static int tlp_row_at(const void *data, size_t size,
                      const r6_tlp_header_t *header,
                      const r6_tlp_section_t *section, uint32_t local,
                      r6_tlp_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tlp_row_t row;
    uint32_t length;
    int result;
    if (local >= section->row_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&row, bytes + tlp_rows_base() +
              (size_t)(section->row_base + local) * R6_TLP_ROW_SIZE,
              sizeof(row));
    if (row.line != section->line + 2u + local) {
        return R6_ERR_FORMAT;
    }
    result = tlp_token_length(data, header, row.token0_offset, &length);
    if (result != R6_OK) {
        return result;
    }
    result = tlp_token_length(data, header, row.token1_offset, &length);
    if (result != R6_OK) {
        return result;
    }
    result = tlp_token_length(data, header, row.token2_offset, &length);
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int tlp_section_for_row(const void *data, size_t size,
                               const r6_tlp_header_t *header, uint32_t index,
                               r6_tlp_section_t *out) {
    uint32_t low = 0;
    uint32_t high = header->section_count;
    r6_tlp_section_t section;
    while (low < high) {
        uint32_t mid = low + (high - low) / 2u;
        if (tlp_section_at(data, size, header, mid, &section) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        if (section.row_base <= index) {
            low = mid + 1u;
        } else {
            high = mid;
        }
    }
    if (!low ||
            tlp_section_at(data, size, header, low - 1u, &section) != R6_OK ||
            section.kind != 0u || index - section.row_base >= section.row_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &section, sizeof(section));
    return R6_OK;
}

int r6_tlp_parse(const void *data, size_t size, r6_tlp_header_t *out) {
    r6_tlp_header_t header;
    r6_tlp_file_t file;
    r6_tlp_section_t section;
    r6_tlp_row_t row;
    uint32_t source = 0;
    uint32_t lines = 0;
    uint32_t sections = 0;
    uint32_t lists = 0;
    uint32_t scalars = 0;
    uint32_t rows = 0;
    uint32_t at;
    uint32_t local;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = tlp_file_at(data, size, &header, at, &file);
        if (result != R6_OK || file.section_base != sections) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        lines += file.lines;
        sections += file.section_count;
    }
    if (source != header.source_bytes || lines != header.line_count ||
            sections != header.section_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.section_count; at++) {
        result = tlp_section_at(data, size, &header, at, &section);
        if (result != R6_OK || section.row_base != rows) {
            return R6_ERR_FORMAT;
        }
        if (section.kind == 0u) {
            lists++;
            for (local = 0; local < section.row_count; local++) {
                result = tlp_row_at(data, size, &header, &section, local, &row);
                if (result != R6_OK) {
                    return result;
                }
            }
            rows += section.row_count;
        } else {
            scalars++;
        }
    }
    if (lists != header.list_count || scalars != header.scalar_count ||
            rows != header.row_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_tlp_file(const void *data, size_t size, uint32_t index,
                r6_tlp_file_t *out) {
    r6_tlp_header_t header;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return tlp_file_at(data, size, &header, index, out);
}

int r6_tlp_name(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_tlp_header_t header;
    r6_tlp_file_t file;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = tlp_file_at(data, size, &header, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return tlp_span(data, &header, file.name_offset, file.name_length,
                    0, out, capacity);
}

int r6_tlp_car_id(const void *data, size_t size, uint32_t index,
                  char *out, size_t capacity) {
    r6_tlp_header_t header;
    r6_tlp_file_t file;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = tlp_file_at(data, size, &header, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return tlp_span(data, &header, file.car_id_offset, file.car_id_length,
                    0, out, capacity);
}

int r6_tlp_section(const void *data, size_t size, uint32_t index,
                   r6_tlp_section_t *out) {
    r6_tlp_header_t header;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return tlp_section_at(data, size, &header, index, out);
}

int r6_tlp_key(const void *data, size_t size, uint32_t index,
               char *out, size_t capacity) {
    r6_tlp_header_t header;
    r6_tlp_section_t section;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = tlp_section_at(data, size, &header, index, &section);
    if (result != R6_OK) {
        return result;
    }
    return tlp_span(data, &header, section.key_offset, section.key_length,
                    0, out, capacity);
}

int r6_tlp_value(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    r6_tlp_header_t header;
    r6_tlp_section_t section;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = tlp_section_at(data, size, &header, index, &section);
    if (result != R6_OK) {
        return result;
    }
    if (section.kind != 1u) {
        return R6_ERR_ARG;
    }
    return tlp_span(data, &header, section.value_offset,
                    section.value_length, 1, out, capacity);
}

int r6_tlp_row(const void *data, size_t size, uint32_t index,
               r6_tlp_row_t *out) {
    r6_tlp_header_t header;
    r6_tlp_section_t section;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.row_count || !out) {
        return R6_ERR_ARG;
    }
    result = tlp_section_for_row(data, size, &header, index, &section);
    if (result != R6_OK) {
        return result;
    }
    return tlp_row_at(data, size, &header, &section,
                      index - section.row_base, out);
}

int r6_tlp_token(const void *data, size_t size, uint32_t index,
                 uint32_t slot, char *out, size_t capacity) {
    r6_tlp_header_t header;
    r6_tlp_row_t row;
    uint32_t offset;
    uint32_t length;
    int result = tlp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = r6_tlp_row(data, size, index, &row);
    if (result != R6_OK) {
        return result;
    }
    if (slot > 2u) {
        return R6_ERR_ARG;
    }
    offset = slot == 0u ? row.token0_offset :
             (slot == 1u ? row.token1_offset : row.token2_offset);
    result = tlp_token_length(data, &header, offset, &length);
    if (result != R6_OK) {
        return result;
    }
    return tlp_span(data, &header, offset, length, 1, out, capacity);
}
