/* Bounds-checked reader for packed Scene.Lua descriptor facts. */

#include "r6/r6_scene_descriptors_catalog.h"

#include "core/internal.h"

enum {
    R6_SCD_HEADER_SIZE = 20,
    R6_SCD_FILE_SIZE = 36,
    R6_SCD_FILES = 70,
    R6_SCD_MAX_STRING = 128
};

static const unsigned char scd_magic[8] = {
    'R', '6', 'S', 'C', 'D', 0, 1, 0
};

static const char scd_root_prefix[] = "data_jp/scene/";
static const char scd_environment[] = "/Environment.Lua";

static int scd_header(const void *data, size_t size,
                      r6_scene_descriptors_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_descriptors_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SCD_HEADER_SIZE ||
            r6_memcmp(bytes, scd_magic, sizeof(scd_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_SCD_FILES ||
            !r6_u32(bytes, 16)) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    base = R6_SCD_HEADER_SIZE +
           (size_t)header.file_count * R6_SCD_FILE_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int scd_string(const void *data,
                      const r6_scene_descriptors_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = R6_SCD_HEADER_SIZE +
                  (size_t)header->file_count * R6_SCD_FILE_SIZE;
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_SCD_MAX_STRING || (size_t)offset < base ||
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

static int scd_copy(const void *data,
                    const r6_scene_descriptors_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = scd_string(data, header, offset, length);
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

static int scd_file(const void *data, size_t size, uint32_t index,
                    r6_scene_descriptors_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_descriptors_header_t header;
    r6_scene_descriptors_file_t file;
    size_t at;
    int result = scd_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_SCD_HEADER_SIZE + (size_t)index * R6_SCD_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || file.event_num != 0u || file.event_count != 0u ||
            file.path_length < 4 ||
            scd_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".Lua", 4) != 0 ||
            file.root_length <= sizeof(scd_root_prefix) - 1u ||
            r6_memcmp(bytes + file.root_offset, scd_root_prefix,
                      sizeof(scd_root_prefix) - 1u) != 0 ||
            scd_string(data, &header, file.root_offset,
                       file.root_length) != R6_OK ||
            file.environment_length != sizeof(scd_environment) - 1u ||
            r6_memcmp(bytes + file.environment_offset, scd_environment,
                      sizeof(scd_environment) - 1u) != 0 ||
            scd_string(data, &header, file.environment_offset,
                       file.environment_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int scd_field(const void *data, size_t size, uint32_t index,
                     uint32_t offset, uint32_t length,
                     char *out, size_t capacity) {
    r6_scene_descriptors_header_t header;
    int result = scd_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    return scd_copy(data, &header, offset, length, out, capacity);
}

int r6_scene_descriptors_parse(const void *data, size_t size,
                               r6_scene_descriptors_header_t *out) {
    r6_scene_descriptors_header_t header;
    r6_scene_descriptors_file_t file;
    uint32_t at;
    int result = scd_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = scd_file(data, size, at, &file);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_scene_descriptors_file(const void *data, size_t size, uint32_t index,
                              r6_scene_descriptors_file_t *out) {
    return scd_file(data, size, index, out);
}

int r6_scene_descriptors_path(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity) {
    r6_scene_descriptors_header_t header;
    r6_scene_descriptors_file_t file;
    int result = scd_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = scd_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return scd_field(data, size, index, file.path_offset,
                     file.path_length, out, capacity);
}

int r6_scene_descriptors_root(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity) {
    r6_scene_descriptors_header_t header;
    r6_scene_descriptors_file_t file;
    int result = scd_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = scd_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return scd_field(data, size, index, file.root_offset,
                     file.root_length, out, capacity);
}

int r6_scene_descriptors_environment(const void *data, size_t size,
                                     uint32_t index, char *out,
                                     size_t capacity) {
    r6_scene_descriptors_header_t header;
    r6_scene_descriptors_file_t file;
    int result = scd_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = scd_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return scd_field(data, size, index, file.environment_offset,
                     file.environment_length, out, capacity);
}
