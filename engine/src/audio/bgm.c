/* Bounds-checked reader for packed BGM id/name/path rows. */

#include "core/internal.h"
#include "r6/r6_bgm.h"

static const unsigned char bgm_magic[8] = {
    'R', '6', 'B', 'G', 'M', 0, 1, 0
};

static int bgm_span(const unsigned char *bytes, size_t size, uint32_t offset,
                    const char **text, size_t *length) {
    size_t i;
    if (!bytes || !text || !length || offset >= size) {
        return R6_ERR_ARG;
    }
    for (i = offset; i < size && bytes[i]; i++) {
        /* scan inside the caller-owned blob */
    }
    if (i >= size) {
        return R6_ERR_FORMAT;
    }
    *text = (const char *)bytes + offset;
    *length = i - offset;
    return R6_OK;
}

int r6_bgm_parse(const void *data, size_t size, r6_bgm_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t count;
    uint32_t id_first;
    uint32_t strings_off;
    uint32_t strings_size;
    uint64_t required;
    if (!out || !bytes || size < R6_BGM_HEADER_SIZE ||
        r6_memcmp(bytes, bgm_magic, sizeof(bgm_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u || r6_u32(bytes, 28) != 0u) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(bytes, 12);
    id_first = r6_u32(bytes, 16);
    strings_off = r6_u32(bytes, 20);
    strings_size = r6_u32(bytes, 24);
    required = R6_BGM_HEADER_SIZE + (uint64_t)count * R6_BGM_RECORD_SIZE;
    if (count == 0 || (uint64_t)id_first + count > 0xffffu ||
        strings_off != required || strings_size == 0 ||
        (uint64_t)strings_off + strings_size != size || bytes[size - 1] != 0) {
        return R6_ERR_FORMAT;
    }
    out->version = 1;
    out->count = count;
    out->id_first = id_first;
    out->strings_off = strings_off;
    out->strings_size = strings_size;
    return R6_OK;
}

const char *r6_bgm_string(const void *data, size_t size, uint32_t offset) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_bgm_header header;
    const char *text = NULL;
    size_t length = 0;
    if (r6_bgm_parse(data, size, &header) != R6_OK ||
        offset < header.strings_off || offset >= size ||
        bgm_span(bytes, size, offset, &text, &length) != R6_OK) {
        return NULL;
    }
    return text;
}

static int bgm_record(const unsigned char *bytes, const r6_bgm_header *header,
                      uint32_t index, r6_bgm_record *out) {
    const unsigned char *at;
    const char *text;
    size_t length;
    if (!out || index >= header->count) {
        return R6_ERR_ARG;
    }
    at = bytes + R6_BGM_HEADER_SIZE + (size_t)index * R6_BGM_RECORD_SIZE;
    r6_memcpy(out, at, R6_BGM_RECORD_SIZE);
    if (out->id < header->id_first ||
        (uint32_t)out->id >= header->id_first + header->count ||
        out->name_off < header->strings_off ||
        out->path_off < header->strings_off ||
        bgm_span(bytes, header->strings_off + header->strings_size,
                 out->name_off, &text, &length) != R6_OK ||
        bgm_span(bytes, header->strings_off + header->strings_size,
                 out->path_off, &text, &length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_bgm_find_id(const void *data, size_t size, uint16_t id,
                   r6_bgm_record *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_bgm_header header;
    r6_bgm_record record;
    uint32_t index;
    int rc;
    if (!out || r6_bgm_parse(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    if (id < header.id_first ||
        (uint32_t)id >= header.id_first + header.count) {
        return R6_ERR_NOT_FOUND;
    }
    index = (uint32_t)id - header.id_first;
    rc = bgm_record(bytes, &header, index, &record);
    if (rc != R6_OK || record.id != id) {
        return rc == R6_OK ? R6_ERR_FORMAT : rc;
    }
    *out = record;
    return R6_OK;
}

int r6_bgm_find_name(const void *data, size_t size, const char *name,
                     r6_bgm_record *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_bgm_header header;
    r6_bgm_record record;
    const char *text;
    size_t length;
    size_t needle = 0;
    uint32_t index;
    int rc;
    if (!out || !name || r6_bgm_parse(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    while (name[needle]) {
        needle++;
    }
    if (needle == 0) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < header.count; index++) {
        rc = bgm_record(bytes, &header, index, &record);
        if (rc != R6_OK) {
            return rc;
        }
        rc = bgm_span(bytes, header.strings_off + header.strings_size,
                      record.name_off, &text, &length);
        if (rc != R6_OK) {
            return rc;
        }
        if (length >= needle) {
            size_t i;
            for (i = 0; i + needle <= length; i++) {
                if (r6_memcmp(text + i, name, needle) == 0) {
                    *out = record;
                    return R6_OK;
                }
            }
        }
    }
    return R6_ERR_NOT_FOUND;
}
