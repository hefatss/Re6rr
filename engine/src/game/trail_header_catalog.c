/* Bounds-checked reader for the packed Enma trail header inventory. */

#include "r6/r6_trail_header_catalog.h"

#include "core/internal.h"

enum {
    R6_TH_HEADER_SIZE = 44,
    R6_TH_FILE_SIZE = 40,
    R6_TH_NAME_SIZE = 12,
    R6_TH_FILES = 2,
    R6_TH_NAMES = 8,
    R6_TH_SOURCE = 207664,
    R6_TH_RECORDS = 3991,
    R6_TH_RECORD_SIZE = 52,
    R6_TH_MARKER_WORD = 3,
    R6_TH_MAX_STRING = 96
};

static const unsigned char th_magic[8] = {
    'R', '6', 'T', 'H', 0, 1, 0, 0
};

static const uint32_t th_sizes[2] = {34414u, 173250u};
static const uint32_t th_links[2] = {1u, 5u};
static const uint32_t th_records[2] = {661u, 3330u};
static const uint32_t th_trailers[2] = {0x00113aebu, 0x00536b19u};

static size_t th_files_base(void) {
    return R6_TH_HEADER_SIZE;
}

static size_t th_names_base(void) {
    return th_files_base() + R6_TH_FILES * R6_TH_FILE_SIZE;
}

static size_t th_strings_base(void) {
    return th_names_base() + R6_TH_NAMES * R6_TH_NAME_SIZE;
}

static int th_header(const void *data, size_t size, r6_th_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_th_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_TH_HEADER_SIZE ||
            r6_memcmp(bytes, th_magic, sizeof(th_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_TH_FILES ||
            r6_u32(bytes, 16) != R6_TH_NAMES ||
            r6_u32(bytes, 20) != R6_TH_SOURCE ||
            r6_u32(bytes, 24) != R6_TH_RECORDS ||
            r6_u32(bytes, 28) != R6_TH_RECORD_SIZE || !r6_u32(bytes, 32) ||
            r6_u32(bytes, 36) != R6_TH_MARKER_WORD ||
            r6_u32(bytes, 40) != 0u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_TH_FILES;
    header.name_count = R6_TH_NAMES;
    header.source_bytes = R6_TH_SOURCE;
    header.record_count = R6_TH_RECORDS;
    header.record_size = R6_TH_RECORD_SIZE;
    header.string_size = r6_u32(bytes, 32);
    header.marker_word = R6_TH_MARKER_WORD;
    header.reserved = 0u;
    base = th_strings_base() + header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int th_string(const void *data, const r6_th_header_t *header,
                     uint32_t offset, uint32_t length, int dotted,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = th_strings_base();
    size_t end = base + header->string_size;
    uint32_t at;
    if (!length || length > R6_TH_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (value < 0x20u || value > 0x7eu ||
                (dotted && value == '/')) {
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

static int th_file(const void *data, size_t size, uint32_t index,
                   r6_th_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_th_header_t header;
    r6_th_file_t file;
    char path[R6_TH_MAX_STRING + 1];
    int result = th_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + th_files_base() +
              (size_t)index * R6_TH_FILE_SIZE, sizeof(file));
    result = th_string(data, &header, file.name_offset, file.name_length,
                       0, path, sizeof(path));
    if (result != R6_OK || file.name_length < 6 ||
            r6_memcmp(path + file.name_length - 6, ".trail", 6) != 0 ||
            file.size != th_sizes[index] || file.links != th_links[index] ||
            file.name_count != th_links[index] + 1u ||
            file.record_count != th_records[index] ||
            file.trailer != th_trailers[index] ||
            file.marker_word != R6_TH_MARKER_WORD) {
        return result != R6_OK ? result : R6_ERR_FORMAT;
    }
    if (file.name_base != (index == 0u ? 0u : th_links[0] + 1u)) {
        return R6_ERR_FORMAT;
    }
    if (file.marker_offset + 12u +
            file.record_count * R6_TH_RECORD_SIZE + 4u != file.size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int th_name(const void *data, const r6_th_header_t *header,
                   uint32_t index, r6_th_name_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_th_name_t name;
    char text[R6_TH_MAX_STRING + 1];
    if (index >= header->name_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&name, bytes + th_names_base() +
              (size_t)index * R6_TH_NAME_SIZE, sizeof(name));
    if (th_string(data, header, name.name_offset, name.name_length,
                  1, text, sizeof(text)) != R6_OK ||
            name.source_offset < 8u) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &name, sizeof(name));
    return R6_OK;
}

int r6_th_parse(const void *data, size_t size, r6_th_header_t *out) {
    r6_th_header_t header;
    r6_th_file_t file;
    r6_th_name_t name;
    uint32_t names = 0;
    uint32_t records = 0;
    uint32_t source = 0;
    uint32_t at;
    uint32_t slot;
    uint32_t expected;
    int result = th_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = th_file(data, size, at, &file);
        if (result != R6_OK || file.name_base != names) {
            return R6_ERR_FORMAT;
        }
        expected = 8u;
        for (slot = 0; slot < file.name_count; slot++) {
            result = th_name(data, &header, names + slot, &name);
            if (result != R6_OK || name.source_offset != expected) {
                return R6_ERR_FORMAT;
            }
            expected += name.name_length + 1u;
        }
        if (expected != file.marker_offset) {
            return R6_ERR_FORMAT;
        }
        names += file.name_count;
        records += file.record_count;
        source += file.size;
    }
    if (names != header.name_count || records != header.record_count ||
            source != header.source_bytes) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_th_file(const void *data, size_t size, uint32_t index,
               r6_th_file_t *out) {
    return th_file(data, size, index, out);
}

int r6_th_path(const void *data, size_t size, uint32_t index,
               char *out, size_t capacity) {
    r6_th_header_t header;
    r6_th_file_t file;
    int result = th_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = th_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return th_string(data, &header, file.name_offset, file.name_length,
                     0, out, capacity);
}

int r6_th_name(const void *data, size_t size, uint32_t index,
               r6_th_name_t *out) {
    r6_th_header_t header;
    int result = th_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return th_name(data, &header, index, out);
}

int r6_th_name_text(const void *data, size_t size, uint32_t index,
                    char *out, size_t capacity) {
    r6_th_header_t header;
    r6_th_name_t name;
    int result = th_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = th_name(data, &header, index, &name);
    if (result != R6_OK) {
        return result;
    }
    return th_string(data, &header, name.name_offset, name.name_length,
                     1, out, capacity);
}
