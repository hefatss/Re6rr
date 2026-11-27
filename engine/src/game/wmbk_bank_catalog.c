/* Bounds-checked reader for packed root WMBK bank facts. Only copied paths,
 * gzip header words and record headers cross the bridge. */

#include "r6/r6_wmbk_bank_catalog.h"

#include "core/internal.h"

enum {
    R6_WMBK_HEADER_SIZE = 32,
    R6_WMBK_FILE_SIZE = 44,
    R6_WMBK_RECORD_SIZE = 20
};

static const unsigned char wmbk_magic[8] = {
    'R', '6', 'W', 'B', 'K', 0, 1, 0
};

static const unsigned char wmbk_record_magic[4] = {'W', 'M', 'B', 'K'};

static size_t wmbk_string_base(const r6_wmbk_header_t *header) {
    return R6_WMBK_HEADER_SIZE +
           (size_t)header->file_count * R6_WMBK_FILE_SIZE +
           (size_t)header->record_count * R6_WMBK_RECORD_SIZE;
}

static int wmbk_header(const void *data, size_t size,
                       r6_wmbk_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_wmbk_header_t header;
    size_t files;
    size_t records;
    size_t base;
    size_t end;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_WMBK_HEADER_SIZE ||
            r6_memcmp(bytes, wmbk_magic, sizeof(wmbk_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.record_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.compressed_total = r6_u32(bytes, 24);
    header.inflated_total = r6_u32(bytes, 28);
    if (!header.file_count || !header.record_count || !header.string_size ||
            header.file_count > ((size_t)-1 - R6_WMBK_HEADER_SIZE) /
                                R6_WMBK_FILE_SIZE ||
            header.record_count > ((size_t)-1 - R6_WMBK_HEADER_SIZE -
                                   (size_t)header.file_count *
                                   R6_WMBK_FILE_SIZE) /
                                  R6_WMBK_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_WMBK_FILE_SIZE;
    records = (size_t)header.record_count * R6_WMBK_RECORD_SIZE;
    if (records > (size_t)-1 - R6_WMBK_HEADER_SIZE - files) {
        return R6_ERR_FORMAT;
    }
    base = R6_WMBK_HEADER_SIZE + files + records;
    end = base + header.string_size;
    if (end < base || end != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int wmbk_validate_string(const void *data,
                                const r6_wmbk_header_t *header,
                                uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = wmbk_string_base(header);
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

static int wmbk_file_row(const void *data,
                         const r6_wmbk_header_t *header, uint32_t index,
                         r6_wmbk_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_wmbk_file_t file;
    int result = wmbk_validate_string(data, header,
                                      r6_u32(data, R6_WMBK_HEADER_SIZE +
                                             (size_t)index * R6_WMBK_FILE_SIZE),
                                      r6_u32(data, R6_WMBK_HEADER_SIZE +
                                             (size_t)index * R6_WMBK_FILE_SIZE + 4));
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(&file, bytes + R6_WMBK_HEADER_SIZE +
             (size_t)index * R6_WMBK_FILE_SIZE, sizeof(file));
    if (file.path_length < 12 || file.compressed < 18 || !file.inflated ||
            file.isize != file.inflated || file.flg != 0 || file.xfl != 0 ||
            file.os != 255 ||
            (r6_memcmp(bytes + file.path_offset, "FBK_W6W_", 8) != 0 &&
             r6_memcmp(bytes + file.path_offset, "GBK_W6W_", 8) != 0) ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".bin", 4) != 0 ||
            file.record_first > header->record_count ||
            file.record_count > header->record_count - file.record_first) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int wmbk_record_row(const void *data,
                           const r6_wmbk_header_t *header, uint32_t index,
                           r6_wmbk_record_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_wmbk_record_t record;
    r6_wmbk_file_t file;
    size_t row = R6_WMBK_HEADER_SIZE +
                 (size_t)header->file_count * R6_WMBK_FILE_SIZE +
                 (size_t)index * R6_WMBK_RECORD_SIZE;
    int result;
    r6_memcpy(&record, bytes + row, sizeof(record));
    if (record.file_index >= header->file_count || record.version != 1u ||
            r6_memcmp(bytes + row + 8, wmbk_record_magic,
                      sizeof(wmbk_record_magic)) != 0 ||
            record.payload_length < 12) {
        return R6_ERR_FORMAT;
    }
    result = wmbk_file_row(data, header, record.file_index, &file);
    if (result != R6_OK) {
        return result;
    }
    if (record.byte_offset > file.inflated ||
            8u + record.payload_length > file.inflated - record.byte_offset) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &record, sizeof(record));
    }
    return R6_OK;
}

static int wmbk_layout(const void *data, size_t size,
                       r6_wmbk_header_t *out) {
    r6_wmbk_header_t header;
    uint32_t at;
    uint32_t compressed = 0;
    uint32_t inflated = 0;
    uint32_t next = 0;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = wmbk_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_wmbk_file_t file;
        uint32_t offset = 0;
        uint32_t row;
        result = wmbk_file_row(data, &header, at, &file);
        if (result != R6_OK || file.record_first != next ||
                file.record_count == 0) {
            return R6_ERR_FORMAT;
        }
        for (row = 0; row < file.record_count; row++) {
            r6_wmbk_record_t record;
            result = wmbk_record_row(data, &header,
                                     file.record_first + row, &record);
            if (result != R6_OK || record.file_index != at ||
                    record.byte_offset != offset) {
                return R6_ERR_FORMAT;
            }
            offset += 8u + record.payload_length;
        }
        if (offset != file.inflated) {
            return R6_ERR_FORMAT;
        }
        next += file.record_count;
        compressed += file.compressed;
        inflated += file.inflated;
    }
    if (next != header.record_count || compressed != header.compressed_total ||
            inflated != header.inflated_total) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_wmbk_bank_parse(const void *data, size_t size,
                       r6_wmbk_header_t *out) {
    return wmbk_layout(data, size, out);
}

int r6_wmbk_bank_file(const void *data, size_t size, uint32_t index,
                      r6_wmbk_file_t *out) {
    r6_wmbk_header_t header;
    int result = wmbk_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return wmbk_file_row(data, &header, index, out);
}

int r6_wmbk_bank_path(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_wmbk_header_t header;
    size_t row;
    int result = wmbk_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_WMBK_HEADER_SIZE + (size_t)index * R6_WMBK_FILE_SIZE;
    result = wmbk_validate_string(data, &header, r6_u32(bytes, row),
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

int r6_wmbk_bank_record(const void *data, size_t size, uint32_t index,
                        r6_wmbk_record_t *out) {
    r6_wmbk_header_t header;
    int result = wmbk_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.record_count || !out) {
        return R6_ERR_ARG;
    }
    return wmbk_record_row(data, &header, index, out);
}
