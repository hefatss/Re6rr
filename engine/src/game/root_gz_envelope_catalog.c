/* Bounds-checked reader for the packed root gzip envelope inventory. */

#include "r6/r6_root_gz_envelope_catalog.h"

#include "core/internal.h"

enum {
    R6_RGZ_HEADER_SIZE = 32,
    R6_RGZ_FILE_SIZE = 32,
    R6_RGZ_FILES = 25,
    R6_RGZ_VALID = 20,
    R6_RGZ_EMPTY = 5,
    R6_RGZ_SOURCE = 1239,
    R6_RGZ_MAX_STRING = 96
};

static const unsigned char rgz_magic[8] = {
    'R', '6', 'R', 'G', 'Z', 0, 1, 0
};

static int rgz_header(const void *data, size_t size,
                      r6_root_gz_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_gz_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_RGZ_HEADER_SIZE ||
            r6_memcmp(bytes, rgz_magic, sizeof(rgz_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_RGZ_FILES ||
            r6_u32(bytes, 16) != R6_RGZ_VALID ||
            r6_u32(bytes, 20) != R6_RGZ_EMPTY ||
            r6_u32(bytes, 24) != R6_RGZ_SOURCE || !r6_u32(bytes, 28)) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_RGZ_FILES;
    header.valid_count = R6_RGZ_VALID;
    header.empty_count = R6_RGZ_EMPTY;
    header.source_bytes = R6_RGZ_SOURCE;
    header.string_size = r6_u32(bytes, 28);
    base = R6_RGZ_HEADER_SIZE + R6_RGZ_FILES * R6_RGZ_FILE_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int rgz_string(const void *data,
                      const r6_root_gz_header_t *header,
                      uint32_t offset, uint32_t length, char *out,
                      size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = R6_RGZ_HEADER_SIZE + R6_RGZ_FILES * R6_RGZ_FILE_SIZE;
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_RGZ_MAX_STRING || (size_t)offset < base ||
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
    if (!out || !capacity || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int rgz_file(const void *data, size_t size, uint32_t index,
                    r6_root_gz_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_gz_header_t header;
    r6_root_gz_file_t file;
    int result = rgz_header(data, size, &header);
    char name[R6_RGZ_MAX_STRING + 1];
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + R6_RGZ_HEADER_SIZE +
              (size_t)index * R6_RGZ_FILE_SIZE, sizeof(file));
    result = rgz_string(data, &header, file.name_offset, file.name_length,
                        name, sizeof(name));
    if (result != R6_OK || file.name_length < 4 ||
            r6_memcmp(name + file.name_length - 3, ".gz", 3) != 0 ||
            file.valid > 1u || file.header_flags > 0xffu) {
        return result != R6_OK ? result : R6_ERR_FORMAT;
    }
    if (!file.valid) {
        if (file.size || file.mtime || file.crc32 || file.isize ||
                file.header_flags) {
            return R6_ERR_FORMAT;
        }
    } else {
        if (file.size < 18u || file.header_flags != 0u || !file.isize) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

int r6_root_gz_parse(const void *data, size_t size,
                     r6_root_gz_header_t *out) {
    r6_root_gz_header_t header;
    r6_root_gz_file_t file;
    uint32_t source = 0;
    uint32_t valid = 0;
    uint32_t at;
    int result = rgz_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = rgz_file(data, size, at, &file);
        if (result != R6_OK) {
            return result;
        }
        source += file.size;
        valid += file.valid;
    }
    if (source != header.source_bytes || valid != header.valid_count ||
            header.empty_count != header.file_count - header.valid_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_root_gz_file(const void *data, size_t size, uint32_t index,
                    r6_root_gz_file_t *out) {
    return rgz_file(data, size, index, out);
}

int r6_root_gz_name(const void *data, size_t size, uint32_t index,
                    char *out, size_t capacity) {
    r6_root_gz_header_t header;
    r6_root_gz_file_t file;
    int result = rgz_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = rgz_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return rgz_string(data, &header, file.name_offset, file.name_length,
                      out, capacity);
}
