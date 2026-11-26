/* Bounds-checked reader for the packed engine-sound selection table. */

#include "core/internal.h"
#include "r6/r6_engine_sound.h"

static const unsigned char esnd_magic[8] = {
    'R', '6', 'E', 'S', 'N', 'D', 0, 1
};

static int esnd_header(const void *data, size_t size, r6_esnd_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t mappings;
    uint32_t sounds;
    uint32_t tunes;
    uint32_t layers;
    uint64_t required;
    if (!bytes || !out || size < R6_ESND_HEADER_SIZE ||
        r6_memcmp(bytes, esnd_magic, sizeof(esnd_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u || r6_u32(bytes, 28) != 0u) {
        return R6_ERR_FORMAT;
    }
    mappings = r6_u32(bytes, 12);
    sounds = r6_u32(bytes, 16);
    tunes = r6_u32(bytes, 20);
    layers = r6_u32(bytes, 24);
    if (mappings == 0 || sounds == 0 || tunes == 0 ||
        layers != sounds * R6_ESND_LAYER_COUNT ||
        mappings % tunes != 0) {
        return R6_ERR_FORMAT;
    }
    required = R6_ESND_HEADER_SIZE +
               (uint64_t)mappings * R6_ESND_MAPPING_SIZE +
               (uint64_t)layers * R6_ESND_LAYER_SIZE;
    if (required != size) {
        return R6_ERR_FORMAT;
    }
    out->mapping_count = mappings;
    out->sound_count = sounds;
    out->tunes_per_car = tunes;
    out->layer_count = layers;
    return R6_OK;
}

int r6_esnd_parse(const void *data, size_t size, r6_esnd_header *out) {
    return esnd_header(data, size, out);
}

int r6_esnd_find(const void *data, size_t size, uint8_t car_type,
                 uint8_t tune, r6_esnd_mapping *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_esnd_header header;
    uint32_t i;
    int rc = esnd_header(data, size, &header);
    if (rc != R6_OK || !out) {
        return rc == R6_OK ? R6_ERR_ARG : rc;
    }
    for (i = 0; i < header.mapping_count; i++) {
        const unsigned char *at = bytes + R6_ESND_HEADER_SIZE +
                                  i * R6_ESND_MAPPING_SIZE;
        if (at[0] == car_type && at[1] == tune && at[2] != 0) {
            r6_memcpy(out, at, R6_ESND_MAPPING_SIZE);
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_esnd_get_layer(const void *data, size_t size, uint16_t engine_sound,
                  uint32_t index, r6_esnd_layer *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_esnd_header header;
    uint64_t at;
    int rc = esnd_header(data, size, &header);
    if (rc != R6_OK || !out) {
        return rc == R6_OK ? R6_ERR_ARG : rc;
    }
    if (engine_sound >= header.sound_count ||
        index >= R6_ESND_LAYER_COUNT) {
        return R6_ERR_ARG;
    }
    at = R6_ESND_HEADER_SIZE +
         (uint64_t)header.mapping_count * R6_ESND_MAPPING_SIZE +
         ((uint64_t)engine_sound * R6_ESND_LAYER_COUNT + index) *
         R6_ESND_LAYER_SIZE;
    if (at > size || (uint64_t)R6_ESND_LAYER_SIZE > size - at) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, bytes + at, R6_ESND_LAYER_SIZE);
    return R6_OK;
}
