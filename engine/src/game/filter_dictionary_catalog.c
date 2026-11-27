/* Bounds-checked reader for packed filter Lua line shapes. Only copied paths,
 * counts, line indices, byte spans and kind/value numbers cross the bridge. */

#include "r6/r6_filter_dictionary_catalog.h"

#include "core/internal.h"

enum {
    R6_FILTER_HEADER_SIZE = 32,
    R6_FILTER_FILE_SIZE = 44,
    R6_FILTER_ROW_SIZE = 24
};

static const unsigned char filter_magic[8] = {
    'R', '6', 'F', 'L', 'T', 0, 1, 0
};

static size_t filter_string_base(const r6_filter_header_t *header) {
    return R6_FILTER_HEADER_SIZE +
           (size_t)header->file_count * R6_FILTER_FILE_SIZE +
           (size_t)header->row_count * R6_FILTER_ROW_SIZE;
}

static int filter_header(const void *data, size_t size,
                         r6_filter_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_filter_header_t header;
    size_t files;
    size_t rows;
    size_t base;
    size_t end;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_FILTER_HEADER_SIZE ||
            r6_memcmp(bytes, filter_magic, sizeof(filter_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.row_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    header.source_lines = r6_u32(bytes, 28);
    if (!header.file_count || !header.row_count || !header.string_size ||
            !header.source_bytes || !header.source_lines ||
            header.file_count > ((size_t)-1 - R6_FILTER_HEADER_SIZE) /
                                R6_FILTER_FILE_SIZE ||
            header.row_count > ((size_t)-1 - R6_FILTER_HEADER_SIZE -
                                (size_t)header.file_count *
                                R6_FILTER_FILE_SIZE) / R6_FILTER_ROW_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_FILTER_FILE_SIZE;
    rows = (size_t)header.row_count * R6_FILTER_ROW_SIZE;
    if (rows > (size_t)-1 - R6_FILTER_HEADER_SIZE - files) {
        return R6_ERR_FORMAT;
    }
    base = R6_FILTER_HEADER_SIZE + files + rows;
    end = base + header.string_size;
    if (end < base || end != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int filter_validate_string(const void *data,
                                  const r6_filter_header_t *header,
                                  uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = filter_string_base(header);
    size_t end = base + header->string_size;
    size_t at;
    if (!length || (size_t)offset < base || (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        if (bytes[(size_t)offset + at] >= 0x80u) {
            return R6_ERR_FORMAT;
        }
    }
    if (bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int filter_file_row(const void *data,
                           const r6_filter_header_t *header, uint32_t index,
                           r6_filter_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_filter_file_t file;
    size_t row = R6_FILTER_HEADER_SIZE + (size_t)index * R6_FILTER_FILE_SIZE;
    int result = filter_validate_string(data, header, r6_u32(bytes, row),
                                        r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(&file, bytes + row, sizeof(file));
    if (!file.source_size || !file.line_count || file.line_count >
            header->source_lines || file.active + file.commented +
            file.bool_count + file.table + file.function > file.row_count ||
            file.row_first > header->row_count ||
            file.row_count > header->row_count - file.row_first) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int filter_row(const void *data, const r6_filter_header_t *header,
                      uint32_t index, r6_filter_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_filter_row_t row;
    size_t at = R6_FILTER_HEADER_SIZE +
                (size_t)header->file_count * R6_FILTER_FILE_SIZE +
                (size_t)index * R6_FILTER_ROW_SIZE;
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (row.file_index >= header->file_count || row.kind > 6u ||
            row.value > 2u ||
            (row.kind == R6_FILTER_KIND_BOOL && row.value > 1u) ||
            (row.kind != R6_FILTER_KIND_BOOL && row.value != 2u)) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &row, sizeof(row));
    }
    return R6_OK;
}

static int filter_layout(const void *data, size_t size,
                         r6_filter_header_t *out) {
    r6_filter_header_t header;
    uint32_t at;
    uint32_t next = 0;
    uint32_t source_bytes = 0;
    uint32_t source_lines = 0;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = filter_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_filter_file_t file;
        uint32_t counts[7];
        uint32_t row;
        uint32_t last_line = 0;
        uint32_t last_offset = 0;
        result = filter_file_row(data, &header, at, &file);
        if (result != R6_OK || file.row_first != next || !file.row_count) {
            return R6_ERR_FORMAT;
        }
        counts[0] = 0;
        counts[1] = 0;
        counts[2] = 0;
        counts[3] = 0;
        counts[4] = 0;
        counts[5] = 0;
        counts[6] = 0;
        for (row = 0; row < file.row_count; row++) {
            r6_filter_row_t item;
            result = filter_row(data, &header, file.row_first + row, &item);
            if (result != R6_OK || item.file_index != at ||
                    item.line_index >= file.line_count ||
                    (row && item.line_index <= last_line) ||
                    item.byte_offset > file.source_size ||
                    item.line_length > file.source_size - item.byte_offset ||
                    item.byte_offset < last_offset ||
                    item.kind > 6u || ++counts[item.kind] > file.row_count) {
                return R6_ERR_FORMAT;
            }
            last_line = item.line_index;
            last_offset = item.byte_offset + item.line_length;
        }
        if (counts[0] != file.table || counts[3] != file.active ||
                counts[4] != file.commented ||
                counts[5] != file.bool_count || counts[6] != file.function) {
            return R6_ERR_FORMAT;
        }
        next += file.row_count;
        source_bytes += file.source_size;
        source_lines += file.line_count;
    }
    if (next != header.row_count || source_bytes != header.source_bytes ||
            source_lines != header.source_lines) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_filter_dictionary_parse(const void *data, size_t size,
                               r6_filter_header_t *out) {
    return filter_layout(data, size, out);
}

int r6_filter_dictionary_file(const void *data, size_t size, uint32_t index,
                              r6_filter_file_t *out) {
    r6_filter_header_t header;
    int result = filter_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return filter_file_row(data, &header, index, out);
}

int r6_filter_dictionary_path(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_filter_header_t header;
    size_t row;
    int result = filter_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_FILTER_HEADER_SIZE + (size_t)index * R6_FILTER_FILE_SIZE;
    result = filter_validate_string(data, &header, r6_u32(bytes, row),
                                    r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)r6_u32(bytes, row + 4) + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + r6_u32(bytes, row), r6_u32(bytes, row + 4));
    out[r6_u32(bytes, row + 4)] = 0;
    return R6_OK;
}

int r6_filter_dictionary_row(const void *data, size_t size, uint32_t index,
                             r6_filter_row_t *out) {
    r6_filter_header_t header;
    int result = filter_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.row_count || !out) {
        return R6_ERR_ARG;
    }
    return filter_row(data, &header, index, out);
}
