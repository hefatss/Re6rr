/* Bounds-checked reader for the packed stage-effect sound catalog. */

#include "r6/r6_stage_effect.h"

#include "core/internal.h"

static const unsigned char stage_magic[8] = {
    'R', '6', 'S', 'T', 'G', 0, 1, 0
};

int r6_stage_effect_parse(const void *data, size_t size,
                          r6_stage_effect_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t count;
    uint32_t strings_off;
    uint32_t strings_size;
    uint64_t required;
    if (!out || !bytes || size < R6_STAGE_EFFECT_HEADER_SIZE ||
        r6_memcmp(bytes, stage_magic, sizeof(stage_magic)) != 0) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(bytes, 12);
    strings_off = r6_u32(bytes, 16);
    strings_size = r6_u32(bytes, 20);
    if (r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    if (strings_off < R6_STAGE_EFFECT_HEADER_SIZE ||
        strings_size < 1u ||
        (uint64_t)strings_off +
            (uint64_t)count * R6_STAGE_EFFECT_RECORD_SIZE > size ||
        (uint64_t)strings_off + strings_size > size) {
        return R6_ERR_FORMAT;
    }
    required = (uint64_t)strings_off + strings_size;
    if (required != size) {
        return R6_ERR_FORMAT;
    }
    out->version = 1u;
    out->count = count;
    out->strings_off = strings_off;
    out->strings_size = strings_size;
    return R6_OK;
}

const char *r6_stage_effect_string(const void *data, size_t size,
                                   uint32_t offset) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t i;
    if (!bytes || offset < R6_STAGE_EFFECT_HEADER_SIZE || offset >= size) {
        return NULL;
    }
    for (i = offset; i < size && bytes[i]; i++) {
        /* scan inside the caller-owned blob */
    }
    return i < size ? (const char *)bytes + offset : NULL;
}

int r6_stage_effect_get(const void *data, size_t size, uint32_t index,
                        r6_stage_effect_record *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_stage_effect_header header;
    const unsigned char *at;
    uint32_t value;
    uint32_t i;
    if (r6_stage_effect_parse(data, size, &header) != R6_OK || !out ||
        index >= header.count) {
        return R6_ERR_ARG;
    }
    at = bytes + R6_STAGE_EFFECT_HEADER_SIZE +
         (size_t)index * R6_STAGE_EFFECT_RECORD_SIZE;
    r6_memset(out, 0, sizeof(*out));
    for (i = 0; i < 5u; i++) {
        value = r6_u32(at, (size_t)i * 4u);
        if (!r6_stage_effect_string(bytes, size, value)) {
            return R6_ERR_FORMAT;
        }
    }
    out->set_off = r6_u32(at, 0);
    out->symbol_off = r6_u32(at, 4);
    out->file_off = r6_u32(at, 8);
    out->tone_name_off = r6_u32(at, 12);
    out->wav_off = r6_u32(at, 16);
    out->bank = r6_u16(at, 20);
    out->tone = r6_u16(at, 22);
    out->native_tone = r6_u16(at, 24);
    out->loop = r6_u16(at, 26);
    r6_memcpy(&out->x, at + 28, sizeof(out->x));
    r6_memcpy(&out->y, at + 32, sizeof(out->y));
    r6_memcpy(&out->z, at + 36, sizeof(out->z));
    return R6_OK;
}

int r6_stage_effect_find_symbol(const void *data, size_t size,
                                const char *symbol,
                                r6_stage_effect_record *out) {
    r6_stage_effect_header header;
    uint32_t index;
    const char *text;
    if (!symbol || r6_stage_effect_parse(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < header.count; index++) {
        r6_stage_effect_record record;
        if (r6_stage_effect_get(data, size, index, &record) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        text = r6_stage_effect_string(data, size, record.symbol_off);
        if (text && r6_strlen(text) == r6_strlen(symbol) &&
            r6_memcmp(text, symbol, r6_strlen(symbol)) == 0) {
            if (out) {
                *out = record;
            }
            return (int)index;
        }
    }
    return R6_ERR_NOT_FOUND;
}
