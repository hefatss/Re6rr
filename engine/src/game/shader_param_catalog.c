/* Bounds-checked reader for packed per-car shader Lua parameter facts. Only
 * copied strings and float32 values cross the bridge. */

#include "r6/r6_shader_param_catalog.h"

#include "core/internal.h"

enum {
    R6_SHP_HEADER_SIZE = 28,
    R6_SHP_FILE_SIZE = 48,
    R6_SHP_VALUE_OFFSET = 16
};

static const unsigned char shp_magic[8] = {
    'R', '6', 'S', 'H', 'P', 0, 1, 0
};

static const unsigned char shp_suffix[20] = {
    '_', 'S', 'h', 'a', 'd', 'e', 'r', 'P', 'a', 'r', 'a', 'm', 'e',
    't', 'e', 'r', '.', 'l', 'u', 'a'
};

static size_t shp_string_base(const r6_shader_param_header_t *header) {
    return R6_SHP_HEADER_SIZE + (size_t)header->count * R6_SHP_FILE_SIZE;
}

static int shp_header(const void *data, size_t size,
                      r6_shader_param_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_shader_param_header_t header;
    size_t base;
    size_t end;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SHP_HEADER_SIZE ||
            r6_memcmp(bytes, shp_magic, sizeof(shp_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.reserved0 = r6_u32(bytes, 20);
    header.reserved1 = r6_u32(bytes, 24);
    if (!header.count || !header.string_size || header.reserved0 ||
            header.reserved1 || header.count >
            ((size_t)-1 - R6_SHP_HEADER_SIZE) / R6_SHP_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    base = R6_SHP_HEADER_SIZE + (size_t)header.count * R6_SHP_FILE_SIZE;
    end = base + header.string_size;
    if (end < base || end != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int shp_validate_string(const void *data,
                               const r6_shader_param_header_t *header,
                               uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = shp_string_base(header);
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

static int shp_file_row(const void *data,
                        const r6_shader_param_header_t *header,
                        uint32_t index, r6_shader_param_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_shader_param_file_t file;
    size_t row = R6_SHP_HEADER_SIZE + (size_t)index * R6_SHP_FILE_SIZE;
    size_t path_end;
    size_t slash;
    uint32_t value;
    int at;
    int result = shp_validate_string(data, header, r6_u32(bytes, row),
                                     r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    result = shp_validate_string(data, header, r6_u32(bytes, row + 8),
                                 r6_u32(bytes, row + 12));
    if (result != R6_OK) {
        return result;
    }
    file.path_offset = r6_u32(bytes, row);
    file.path_length = r6_u32(bytes, row + 4);
    file.model_offset = r6_u32(bytes, row + 8);
    file.model_length = r6_u32(bytes, row + 12);
    path_end = (size_t)file.path_offset + file.path_length;
    if (file.path_length < sizeof(shp_suffix) ||
            r6_memcmp(bytes + path_end - sizeof(shp_suffix), shp_suffix,
                      sizeof(shp_suffix)) != 0) {
        return R6_ERR_FORMAT;
    }
    slash = path_end - sizeof(shp_suffix) - 1u;
    while (slash >= (size_t)file.path_offset && bytes[slash] != '/') {
        slash--;
    }
    if (slash < (size_t)file.path_offset ||
            file.model_length != path_end - sizeof(shp_suffix) - slash - 1u ||
            r6_memcmp(bytes + file.model_offset, bytes + slash + 1u,
                      file.model_length) != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < R6_SHADER_PARAM_COUNT; at++) {
        r6_memcpy(&value, bytes + row + R6_SHP_VALUE_OFFSET + (size_t)at * 4,
                  4);
        if ((value & 0x7f800000u) == 0x7f800000u) {
            return R6_ERR_FORMAT;
        }
        r6_memcpy((unsigned char *)file.values + (size_t)at * 4, &value, 4);
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int shp_layout(const void *data, size_t size,
                      r6_shader_param_header_t *out) {
    r6_shader_param_header_t header;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = shp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.count; at++) {
        result = shp_file_row(data, &header, at, NULL);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_shader_param_parse(const void *data, size_t size,
                          r6_shader_param_header_t *out) {
    return shp_layout(data, size, out);
}

int r6_shader_param_file(const void *data, size_t size, uint32_t index,
                         r6_shader_param_file_t *out) {
    r6_shader_param_header_t header;
    int result = shp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count || !out) {
        return R6_ERR_ARG;
    }
    return shp_file_row(data, &header, index, out);
}

static int shp_copy(const void *data, const r6_shader_param_header_t *header,
                    uint32_t offset, uint32_t length, char *out,
                    size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = shp_validate_string(data, header, offset, length);
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

int r6_shader_param_path(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_shader_param_header_t header;
    size_t row;
    int result = shp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count) {
        return R6_ERR_ARG;
    }
    row = R6_SHP_HEADER_SIZE + (size_t)index * R6_SHP_FILE_SIZE;
    return shp_copy(data, &header, r6_u32(bytes, row),
                    r6_u32(bytes, row + 4), out, capacity);
}

int r6_shader_param_model(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_shader_param_header_t header;
    size_t row;
    int result = shp_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count) {
        return R6_ERR_ARG;
    }
    row = R6_SHP_HEADER_SIZE + (size_t)index * R6_SHP_FILE_SIZE;
    return shp_copy(data, &header, r6_u32(bytes, row + 8),
                    r6_u32(bytes, row + 12), out, capacity);
}
