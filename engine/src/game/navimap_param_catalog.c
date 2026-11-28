/* Bounds-checked reader for packed NavimapParam.lua structural facts. */

#include "r6/r6_navimap_param_catalog.h"

#include "core/internal.h"

enum {
    R6_NVM_HEADER_SIZE = 48,
    R6_NVM_SCALAR_SIZE = 20,
    R6_NVM_SPAN_SIZE = 8,
    R6_NVM_SCALARS = 4,
    R6_NVM_TABLE_VALUES = 11,
    R6_NVM_SOURCE_BYTES = 1137,
    R6_NVM_SOURCE_LINES = 32,
    R6_NVM_MAX_STRING = 96
};

static const unsigned char nvm_magic[8] = {
    'R', '6', 'N', 'V', 'M', 0, 1, 0
};

static const char nvm_table_name[] = "NAVIMAP_USE";

static int nvm_header(const void *data, size_t size,
                      r6_navimap_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_navimap_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_NVM_HEADER_SIZE ||
            r6_memcmp(bytes, nvm_magic, sizeof(nvm_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || !r6_u32(bytes, 12) ||
            r6_u32(bytes, 16) != R6_NVM_SOURCE_BYTES ||
            r6_u32(bytes, 20) != R6_NVM_SOURCE_LINES ||
            r6_u32(bytes, 24) != R6_NVM_SCALARS ||
            r6_u32(bytes, 28) != R6_NVM_TABLE_VALUES) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(&header, bytes + 8, sizeof(header));
    header.version = 1u;
    base = R6_NVM_HEADER_SIZE + R6_NVM_SCALARS * R6_NVM_SCALAR_SIZE +
           R6_NVM_TABLE_VALUES * R6_NVM_SPAN_SIZE + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t nvm_values_base(void) {
    return R6_NVM_HEADER_SIZE + R6_NVM_SCALARS * R6_NVM_SCALAR_SIZE;
}

static size_t nvm_strings_base(void) {
    return nvm_values_base() + R6_NVM_TABLE_VALUES * R6_NVM_SPAN_SIZE;
}

static int nvm_string(const void *data,
                      const r6_navimap_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = nvm_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_NVM_MAX_STRING || (size_t)offset < base ||
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

static int nvm_copy(const void *data,
                    const r6_navimap_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = nvm_string(data, header, offset, length);
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

static int nvm_scalar(const void *data, size_t size, uint32_t index,
                      r6_navimap_scalar_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_navimap_header_t header;
    r6_navimap_scalar_t scalar;
    size_t at;
    int result = nvm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.scalar_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_NVM_HEADER_SIZE + (size_t)index * R6_NVM_SCALAR_SIZE;
    r6_memcpy(&scalar, bytes + at, sizeof(scalar));
    if (scalar.active > 1u || scalar.name_length < 9u ||
            nvm_string(data, &header, scalar.name_offset,
                       scalar.name_length) != R6_OK ||
            r6_memcmp(bytes + scalar.name_offset, "NAVIMAP_", 8) != 0 ||
            !scalar.value_length ||
            nvm_string(data, &header, scalar.value_offset,
                       scalar.value_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < scalar.value_length; at++) {
        if (bytes[scalar.value_offset + at] < '0' ||
                bytes[scalar.value_offset + at] > '9') {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &scalar, sizeof(scalar));
    return R6_OK;
}

static int nvm_table_value(const void *data,
                           const r6_navimap_header_t *header,
                           uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    size_t at = nvm_values_base() + (size_t)index * R6_NVM_SPAN_SIZE;
    if (index >= header->table_count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    if (length != 1u ||
            (bytes[offset] != '0' && bytes[offset] != '1' &&
             bytes[offset] != '2') ||
            nvm_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    return nvm_copy(data, header, offset, length, out, capacity);
}

int r6_navimap_parse(const void *data, size_t size,
                     r6_navimap_header_t *out) {
    r6_navimap_header_t header;
    r6_navimap_scalar_t scalar;
    char text[R6_NVM_MAX_STRING + 1];
    uint32_t at;
    int result = nvm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if (header.path_length < 4 ||
            nvm_string(data, &header, header.path_offset,
                       header.path_length) != R6_OK ||
            r6_memcmp(((const unsigned char *)data) + header.path_offset +
                      header.path_length - 4, ".lua", 4) != 0 ||
            header.table_name_length != sizeof(nvm_table_name) - 1u ||
            nvm_string(data, &header, header.table_name_offset,
                       header.table_name_length) != R6_OK ||
            r6_memcmp(((const unsigned char *)data) +
                      header.table_name_offset, nvm_table_name,
                      sizeof(nvm_table_name) - 1u) != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.scalar_count; at++) {
        result = nvm_scalar(data, size, at, &scalar);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.table_count; at++) {
        result = nvm_table_value(data, &header, at, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_navimap_scalar(const void *data, size_t size, uint32_t index,
                      r6_navimap_scalar_t *out) {
    return nvm_scalar(data, size, index, out);
}

int r6_navimap_path(const void *data, size_t size, char *out,
                    size_t capacity) {
    r6_navimap_header_t header;
    int result = nvm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return nvm_copy(data, &header, header.path_offset, header.path_length,
                    out, capacity);
}

int r6_navimap_table_name(const void *data, size_t size, char *out,
                          size_t capacity) {
    r6_navimap_header_t header;
    int result = nvm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return nvm_copy(data, &header, header.table_name_offset,
                    header.table_name_length, out, capacity);
}

int r6_navimap_scalar_name(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    r6_navimap_header_t header;
    r6_navimap_scalar_t scalar;
    int result = nvm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = nvm_scalar(data, size, index, &scalar);
    if (result != R6_OK) {
        return result;
    }
    return nvm_copy(data, &header, scalar.name_offset, scalar.name_length,
                    out, capacity);
}

int r6_navimap_scalar_value(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity) {
    r6_navimap_header_t header;
    r6_navimap_scalar_t scalar;
    int result = nvm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = nvm_scalar(data, size, index, &scalar);
    if (result != R6_OK) {
        return result;
    }
    return nvm_copy(data, &header, scalar.value_offset, scalar.value_length,
                    out, capacity);
}

int r6_navimap_table_value(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    r6_navimap_header_t header;
    int result = nvm_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return nvm_table_value(data, &header, index, out, capacity);
}
