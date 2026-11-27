/* Bounds-checked reader for packed .nut file-level header facts. Only copied
 * paths, header words and counts cross the bridge. */

#include "r6/r6_nut_file_catalog.h"

#include "core/internal.h"

enum {
    R6_NUTF_HEADER_SIZE = 44,
    R6_NUTF_FILE_SIZE = 76
};

static const unsigned char nutf_magic[8] = {
    'R', '6', 'N', 'T', 'F', 0, 1, 0
};

static const uint32_t nutf_ntwd = 0x4457544eu;
static const uint32_t nutf_ntlx = 0x584c544eu;

static uint64_t nutf_u64(const void *data, size_t offset) {
    return (uint64_t)r6_u32(data, offset) |
           ((uint64_t)r6_u32(data, offset + 4) << 32);
}

static size_t nutf_string_base(const r6_nut_file_header_t *header) {
    return R6_NUTF_HEADER_SIZE + (size_t)header->file_count *
           R6_NUTF_FILE_SIZE;
}

static int nutf_header(const void *data, size_t size,
                       r6_nut_file_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_nut_file_header_t header;
    size_t files;
    size_t base;
    size_t end;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_NUTF_HEADER_SIZE ||
            r6_memcmp(bytes, nutf_magic, sizeof(nutf_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.source_bytes = nutf_u64(bytes, 20);
    header.inflated_bytes = nutf_u64(bytes, 28);
    header.gzip_count = r6_u32(bytes, 36);
    header.exact_count = r6_u32(bytes, 40);
    if (!header.file_count || !header.string_size ||
            header.gzip_count > header.file_count ||
            header.exact_count > header.file_count ||
            header.file_count >
            ((size_t)-1 - R6_NUTF_HEADER_SIZE) / R6_NUTF_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_NUTF_FILE_SIZE;
    base = R6_NUTF_HEADER_SIZE + files;
    if (base > (size_t)-1 - header.string_size) {
        return R6_ERR_FORMAT;
    }
    end = base + header.string_size;
    if (end != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int nutf_validate_string(const void *data,
                                const r6_nut_file_header_t *header,
                                uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = nutf_string_base(header);
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

static int nutf_extension(const unsigned char *bytes, size_t offset,
                          size_t length) {
    static const char suffix[4] = {'.', 'n', 'u', 't'};
    size_t at;
    if (length < 4) {
        return 0;
    }
    for (at = 0; at < 4; at++) {
        unsigned char value = bytes[offset + length - 4 + at];
        if (value >= 'A' && value <= 'Z') {
            value = (unsigned char)(value + ('a' - 'A'));
        }
        if (value != (unsigned char)suffix[at]) {
            return 0;
        }
    }
    return 1;
}

static int nutf_file_row(const void *data,
                         const r6_nut_file_header_t *header, uint32_t index,
                         r6_nut_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_nut_file_t file;
    size_t row = R6_NUTF_HEADER_SIZE + (size_t)index * R6_NUTF_FILE_SIZE;
    uint64_t offset;
    int result = nutf_validate_string(data, header, r6_u32(bytes, row),
                                      r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    file.path_offset = r6_u32(bytes, row);
    file.path_length = r6_u32(bytes, row + 4);
    file.source_size = r6_u32(bytes, row + 8);
    file.inflated_size = r6_u32(bytes, row + 12);
    file.compressed = r6_u32(bytes, row + 16);
    file.container = r6_u32(bytes, row + 20);
    file.version = r6_u32(bytes, row + 24);
    file.entries = r6_u32(bytes, row + 28);
    file.total_lo = r6_u32(bytes, row + 32);
    file.total_hi = r6_u32(bytes, row + 36);
    file.payload_size = r6_u32(bytes, row + 40);
    file.descriptor_size = r6_u32(bytes, row + 44);
    file.packed0 = r6_u32(bytes, row + 48);
    file.packed1 = r6_u32(bytes, row + 52);
    file.gidx_lo = r6_u32(bytes, row + 56);
    file.gidx_hi = r6_u32(bytes, row + 60);
    file.payload_offset_lo = r6_u32(bytes, row + 64);
    file.payload_offset_hi = r6_u32(bytes, row + 68);
    file.exact = r6_u32(bytes, row + 72);
    if (!nutf_extension(bytes, file.path_offset, file.path_length) ||
            file.compressed > 1u ||
            (file.container != nutf_ntwd && file.container != nutf_ntlx) ||
            (file.version != 1u && file.version != 2u) || !file.entries ||
            (file.descriptor_size != 0x50u && file.descriptor_size != 0x60u &&
             file.descriptor_size != 0x70u && file.descriptor_size != 0x80u) ||
            file.source_size < (file.compressed ? 18u : 0x10u) ||
            file.exact > 1u) {
        return R6_ERR_FORMAT;
    }
    offset = (uint64_t)0x10u + (uint64_t)file.entries * file.descriptor_size;
    if (nutf_u64(bytes, row + 64) != offset ||
            nutf_u64(bytes, row + 32) !=
            (uint64_t)file.payload_size + file.descriptor_size ||
            (uint64_t)file.inflated_size < offset) {
        return R6_ERR_FORMAT;
    }
    if (file.exact && (uint64_t)file.inflated_size !=
            offset + (uint64_t)file.entries * file.payload_size) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int nutf_layout(const void *data, size_t size,
                       r6_nut_file_header_t *out) {
    r6_nut_file_header_t header;
    uint64_t source_bytes = 0;
    uint64_t inflated_bytes = 0;
    uint32_t gzip_count = 0;
    uint32_t exact_count = 0;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = nutf_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_nut_file_t file;
        result = nutf_file_row(data, &header, at, &file);
        if (result != R6_OK) {
            return result;
        }
        source_bytes += file.source_size;
        inflated_bytes += file.inflated_size;
        gzip_count += file.compressed;
        exact_count += file.exact;
    }
    if (source_bytes != header.source_bytes ||
            inflated_bytes != header.inflated_bytes ||
            gzip_count != header.gzip_count ||
            exact_count != header.exact_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_nut_file_parse(const void *data, size_t size,
                      r6_nut_file_header_t *out) {
    return nutf_layout(data, size, out);
}

int r6_nut_file(const void *data, size_t size, uint32_t index,
                r6_nut_file_t *out) {
    r6_nut_file_header_t header;
    int result = nutf_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return nutf_file_row(data, &header, index, out);
}

int r6_nut_file_path(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_nut_file_header_t header;
    size_t row;
    int result = nutf_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_NUTF_HEADER_SIZE + (size_t)index * R6_NUTF_FILE_SIZE;
    result = nutf_validate_string(data, &header, r6_u32(bytes, row),
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
