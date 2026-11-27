/* Bounds-checked reader for the packed native story-key inventory. No files,
 * allocation or interpretation of key text beyond exact ASCII lookup. */

#include "r6/r6_story_keys.h"

#include "core/internal.h"

static int keys_layout(const unsigned char *bytes, size_t size,
                       r6_story_keys_catalog *out) {
    static const unsigned char magic[8] = {
        'R', '6', 'S', 'K', 0, 1, 0, 0
    };
    uint32_t native_count;
    uint32_t table_count;
    uint32_t string_count;
    uint32_t strings_off;
    size_t records;
    size_t i;

    if (!bytes || !out || size < R6_STORY_KEYS_HEADER_SIZE ||
            r6_memcmp(bytes, magic, sizeof(magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    native_count = r6_u32(bytes, 12);
    table_count = r6_u32(bytes, 16);
    string_count = r6_u32(bytes, 28);
    strings_off = r6_u32(bytes, 32);
    if (r6_u32(bytes, 24) > native_count || table_count > native_count ||
            native_count > ((size_t)-1 - R6_STORY_KEYS_HEADER_SIZE) /
                           R6_STORY_KEYS_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    records = (size_t)native_count * R6_STORY_KEYS_RECORD_SIZE;
    if ((size_t)strings_off != R6_STORY_KEYS_HEADER_SIZE + records ||
            (size_t)strings_off > size ||
            (size_t)string_count > size - (size_t)strings_off ||
            (size_t)strings_off + (size_t)string_count != size) {
        return R6_ERR_FORMAT;
    }
    for (i = 0; i < native_count; i++) {
        size_t row = R6_STORY_KEYS_HEADER_SIZE + i * R6_STORY_KEYS_RECORD_SIZE;
        uint32_t offset = r6_u32(bytes, row);
        uint16_t length = r6_u16(bytes, row + 4);
        uint8_t source = bytes[row + 6];
        uint32_t table_index = r6_u32(bytes, row + 8);
        if (offset > string_count || length > string_count - offset ||
                bytes[row + 7] != 0u ||
                (source != R6_STORY_KEY_DIRECT &&
                 source != R6_STORY_KEY_TABLE) ||
                (source == R6_STORY_KEY_DIRECT &&
                 table_index != R6_STORY_KEY_NO_TABLE) ||
                (source == R6_STORY_KEY_TABLE && table_index >= table_count)) {
            return R6_ERR_FORMAT;
        }
    }
    out->rows = bytes + R6_STORY_KEYS_HEADER_SIZE;
    out->strings = (const char *)(bytes + strings_off);
    out->native_count = native_count;
    out->table_count = table_count;
    out->msgdb_count = r6_u32(bytes, 20);
    out->matched_count = r6_u32(bytes, 24);
    out->string_count = string_count;
    return R6_OK;
}

int r6_story_keys_parse(const void *data, size_t size,
                        r6_story_keys_catalog *out) {
    if (!data || !out) {
        return R6_ERR_ARG;
    }
    return keys_layout((const unsigned char *)data, size, out);
}

static int keys_string(const r6_story_keys_catalog *catalog, size_t index,
                       uint32_t *offset, uint16_t *length) {
    const unsigned char *row;
    if (!catalog || !catalog->rows || index >= catalog->native_count) {
        return R6_ERR_ARG;
    }
    row = catalog->rows + index * R6_STORY_KEYS_RECORD_SIZE;
    *offset = r6_u32(row, 0);
    *length = r6_u16(row, 4);
    if (*offset > catalog->string_count ||
            *length > catalog->string_count - *offset) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_story_keys_name(const r6_story_keys_catalog *catalog, size_t index,
                       char *out, size_t capacity) {
    uint32_t offset = 0;
    uint16_t length = 0;
    int rc = keys_string(catalog, index, &offset, &length);
    if (rc != R6_OK) {
        return rc;
    }
    if (!out || capacity <= length) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, catalog->strings + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_story_keys_find(const r6_story_keys_catalog *catalog,
                       const char *name) {
    size_t index;
    size_t length;
    if (!catalog || !catalog->rows || !name) {
        return -1;
    }
    length = r6_strlen(name);
    for (index = 0; index < catalog->native_count; index++) {
        uint32_t offset = 0;
        uint16_t row_length = 0;
        if (keys_string(catalog, index, &offset, &row_length) != R6_OK) {
            return -1;
        }
        if ((size_t)row_length == length &&
                r6_memcmp(catalog->strings + offset, name, length) == 0) {
            return (int)index;
        }
    }
    return -1;
}

int r6_story_keys_fact(const r6_story_keys_catalog *catalog, size_t index,
                       uint32_t *source, uint32_t *table_index) {
    const unsigned char *row;
    if (!catalog || !catalog->rows || !source || !table_index ||
            index >= catalog->native_count) {
        return R6_ERR_ARG;
    }
    row = catalog->rows + index * R6_STORY_KEYS_RECORD_SIZE;
    *source = row[6];
    *table_index = r6_u32(row, 8);
    return R6_OK;
}
