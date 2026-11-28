/* Bounds-checked reader for packed root setting.lua.gz structural facts. */

#include "r6/r6_setting_lua_gz_catalog.h"

#include "core/internal.h"

enum {
    R6_SLGH_SIZE = 36,
    R6_SLGF_SIZE = 24,
    R6_SLGS_SIZE = 8,
    R6_SLGH_FILES = 6,
    R6_SLGH_KEYS = 53,
    R6_SLGH_LINES = 60,
    R6_SLGH_SOURCE = 2882,
    R6_SLGH_INFLATED = 7258,
    R6_SLGH_MAX_STRING = 96
};

static const unsigned char slgh_magic[8] = {
    'R', '6', 'S', 'L', 'G', 0, 1, 0
};

static int slgh_header(const void *data, size_t size,
                       r6_setting_lua_gz_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_setting_lua_gz_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SLGH_SIZE ||
            r6_memcmp(bytes, slgh_magic, sizeof(slgh_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_SLGH_FILES ||
            r6_u32(bytes, 16) != R6_SLGH_KEYS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_SLGH_SOURCE ||
            r6_u32(bytes, 28) != R6_SLGH_INFLATED ||
            r6_u32(bytes, 32) != R6_SLGH_LINES) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.key_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    header.inflated_bytes = r6_u32(bytes, 28);
    header.line_count = r6_u32(bytes, 32);
    base = R6_SLGH_SIZE +
           (size_t)header.file_count * R6_SLGF_SIZE +
           ((size_t)header.file_count + 1u) * header.key_count *
           R6_SLGS_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t slgh_keys_base(void) {
    return R6_SLGH_SIZE + R6_SLGH_FILES * R6_SLGF_SIZE;
}

static size_t slgh_values_base(const r6_setting_lua_gz_header_t *header) {
    return slgh_keys_base() + (size_t)header->key_count * R6_SLGS_SIZE;
}

static size_t slgh_strings_base(const r6_setting_lua_gz_header_t *header) {
    return slgh_values_base(header) +
           (size_t)header->file_count * header->key_count * R6_SLGS_SIZE;
}

static int slgh_string(const void *data,
                       const r6_setting_lua_gz_header_t *header,
                       uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = slgh_strings_base(header);
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_SLGH_MAX_STRING || (size_t)offset < base ||
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

static int slgh_copy(const void *data,
                     const r6_setting_lua_gz_header_t *header,
                     uint32_t offset, uint32_t length,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = slgh_string(data, header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int slgh_file(const void *data, size_t size, uint32_t index,
                     r6_setting_lua_gz_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_setting_lua_gz_header_t header;
    r6_setting_lua_gz_file_t file;
    size_t at;
    int result = slgh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_SLGH_SIZE + (size_t)index * R6_SLGF_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (file.compressed_size < 18u || !file.inflated_size ||
            file.path_length < 3 ||
            slgh_string(data, &header, file.path_offset,
                        file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 3,
                      ".gz", 3) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int slgh_key(const void *data,
                    const r6_setting_lua_gz_header_t *header,
                    uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    size_t at;
    unsigned char first;
    if (index >= header->key_count) {
        return R6_ERR_ARG;
    }
    at = slgh_keys_base() + (size_t)index * R6_SLGS_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    if (slgh_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    first = bytes[offset];
    if (!((first >= 'A' && first <= 'Z') ||
          (first >= 'a' && first <= 'z') || first == '_')) {
        return R6_ERR_FORMAT;
    }
    return slgh_copy(data, header, offset, length, out, capacity);
}

static int slgh_value(const void *data,
                      const r6_setting_lua_gz_header_t *header,
                      uint32_t file_index, uint32_t key_index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    size_t at;
    size_t pos;
    if (file_index >= header->file_count || key_index >= header->key_count) {
        return R6_ERR_ARG;
    }
    at = slgh_values_base(header) +
         ((size_t)file_index * header->key_count + key_index) * R6_SLGS_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    if (slgh_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    pos = bytes[offset] == '-' ? 1u : 0u;
    if (pos >= length) {
        return R6_ERR_FORMAT;
    }
    for (; pos < length; pos++) {
        if (bytes[offset + pos] < '0' || bytes[offset + pos] > '9') {
            return R6_ERR_FORMAT;
        }
    }
    return slgh_copy(data, header, offset, length, out, capacity);
}

int r6_setting_lua_gz_parse(const void *data, size_t size,
                            r6_setting_lua_gz_header_t *out) {
    r6_setting_lua_gz_header_t header;
    r6_setting_lua_gz_file_t file;
    char text[R6_SLGH_MAX_STRING + 1];
    uint32_t compressed = 0;
    uint32_t inflated = 0;
    uint32_t at;
    uint32_t key;
    int result = slgh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = slgh_file(data, size, at, &file);
        if (result != R6_OK) {
            return result;
        }
        compressed += file.compressed_size;
        inflated += file.inflated_size;
        for (key = 0; key < header.key_count; key++) {
            result = slgh_value(data, &header, at, key, text, sizeof(text));
            if (result != R6_OK) {
                return result;
            }
        }
    }
    for (key = 0; key < header.key_count; key++) {
        result = slgh_key(data, &header, key, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
    }
    if (compressed != header.source_bytes ||
            inflated != header.inflated_bytes) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_setting_lua_gz_file(const void *data, size_t size, uint32_t index,
                           r6_setting_lua_gz_file_t *out) {
    return slgh_file(data, size, index, out);
}

int r6_setting_lua_gz_path(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_setting_lua_gz_header_t header;
    r6_setting_lua_gz_file_t file;
    int result = slgh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = slgh_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return slgh_copy(data, &header, file.path_offset, file.path_length,
                     out, capacity);
}

int r6_setting_lua_gz_key(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity) {
    r6_setting_lua_gz_header_t header;
    int result = slgh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return slgh_key(data, &header, index, out, capacity);
}

int r6_setting_lua_gz_value(const void *data, size_t size,
                            uint32_t file_index, uint32_t key_index,
                            char *out, size_t capacity) {
    r6_setting_lua_gz_header_t header;
    int result = slgh_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return slgh_value(data, &header, file_index, key_index, out, capacity);
}
