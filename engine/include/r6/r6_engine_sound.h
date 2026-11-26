/* Packed engine-sound selection built from engmap.tbl and emtis.tbl.
 *
 * The blob is derived data: 320 car/tune mappings with 16 layer tones and
 * 224 x 16 resolved layer envelopes. No files, allocation or libm in the core.
 */
#ifndef R6_ENGINE_SOUND_H
#define R6_ENGINE_SOUND_H

#include <stddef.h>
#include <stdint.h>

#include "r6/r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_ESND_HEADER_SIZE 32u
#define R6_ESND_MAPPING_SIZE 72u
#define R6_ESND_LAYER_SIZE 48u
#define R6_ESND_LAYER_COUNT 16u

/* Layer envelope sources, in the order resolved by FUN_1407d2b50. */
enum r6_esnd_source {
    R6_ESND_A = 0,
    R6_ESND_B = 1,
    R6_ESND_D = 2,
    R6_ESND_F = 3,
    R6_ESND_H = 4
};

enum r6_esnd_layer_flags {
    R6_ESND_HAS_RPM = 1,
    R6_ESND_HAS_SCALE = 2
};

typedef struct r6_esnd_header {
    uint32_t mapping_count;
    uint32_t sound_count;
    uint32_t tunes_per_car;
    uint32_t layer_count;
} r6_esnd_header;

typedef struct r6_esnd_mapping {
    uint8_t car_type;
    uint8_t tune;
    uint8_t group;
    uint8_t reserved;
    uint16_t engine_sound;
    uint16_t reserved16;
    int32_t tones[R6_ESND_LAYER_COUNT];
} r6_esnd_mapping;

typedef struct r6_esnd_layer {
    uint8_t layer;
    uint8_t source;
    uint8_t flags;
    uint8_t reserved;
    uint16_t index;
    uint16_t reserved16;
    int32_t tone;
    int32_t envelope[5];
    int32_t rpm_limit;
    float scale;
    int32_t base;
    uint32_t reserved32;
} r6_esnd_layer;

/* Validate the blob layout and return its counts. */
R6_API int r6_esnd_parse(const void *data, size_t size, r6_esnd_header *out);

/* Find one car/tune mapping. Returns R6_ERR_NOT_FOUND when absent. */
R6_API int r6_esnd_find(const void *data, size_t size, uint8_t car_type,
                        uint8_t tune, r6_esnd_mapping *out);

/* Read one resolved layer envelope for an engine sound. */
R6_API int r6_esnd_get_layer(const void *data, size_t size,
                             uint16_t engine_sound,
                         uint32_t index, r6_esnd_layer *out);

#ifdef __cplusplus
}
#endif

#endif
