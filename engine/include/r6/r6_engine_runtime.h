/* Full 16-layer engine-sound state evaluation.
 *
 * Runtime constants and lexical fields come from an R6ERS blob built by
 * tools/engine/engine_runtime_catalog.py; layer envelopes come from R6ESND.
 * pow/exp2 are host callbacks from r6_envelope.h. No files, allocation, CRT
 * or libm.
 */
#ifndef R6_ENGINE_RUNTIME_H
#define R6_ENGINE_RUNTIME_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"
#include "r6_envelope.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_ENGINE_RUNTIME_HEADER_SIZE 32u
#define R6_ENGINE_RUNTIME_SOUND_SIZE 20u
#define R6_ENGINE_LAYER_COUNT 16u

enum {
    R6_ENGINE_SOURCE_A = 0,
    R6_ENGINE_SOURCE_B = 1,
    R6_ENGINE_SOURCE_D = 2,
    R6_ENGINE_SOURCE_F = 3,
    R6_ENGINE_SOURCE_H = 4,
    R6_ENGINE_CONST_REQUEST_AMPLITUDE = 0,
    R6_ENGINE_CONST_REQUEST_PITCH = 1,
    R6_ENGINE_CONST_STATE_THRESHOLD = 2,
    R6_ENGINE_CONST_STATE_MIN_SCALE = 3,
    R6_ENGINE_CONST_BOOST_LIMIT = 12
};

typedef struct r6_engine_runtime_view {
    const unsigned char *data;
    size_t size;
    uint32_t sound_count;
    uint32_t header_count;
    uint32_t constant_count;
    uint32_t sounds_off;
    uint32_t header_off;
    uint32_t constants_off;
} r6_engine_runtime_view;

typedef struct r6_engine_state {
    int32_t rpm;
    int32_t current;
    int32_t request_offset;
    double base[5];
    double layer_base[R6_ENGINE_LAYER_COUNT];
    uint32_t flag;
    double throttle;
    double floors[3][3];
    double smooth34;
    double smooth4f;
    double smooth20;
    double f134;
    double f2d;
    double sub;
    double curve_scale;
} r6_engine_state;

typedef struct r6_engine_layer_result {
    uint32_t layer;
    uint32_t source;
    int32_t tone;
    int32_t pitch;
    int32_t level;
    double volume;
} r6_engine_layer_result;

R6_API int r6_engine_runtime_init(r6_engine_runtime_view *view,
                                  const void *data, size_t size);

/* Lexical sound fields: EMTIS record indices 8 and 13. */
R6_API int r6_engine_runtime_sound(const r6_engine_runtime_view *view,
                                   uint32_t sound, double *lexical8,
                                   double *lexical13);

R6_API int r6_engine_runtime_header(const r6_engine_runtime_view *view,
                                    uint32_t index, double *out);

R6_API int r6_engine_runtime_constant(const r6_engine_runtime_view *view,
                                      uint32_t index, double *out);

/* Neutral state with current = rpm, zero bases and all layer scales at 1. */
R6_API int r6_engine_state_init(r6_engine_state *state, int32_t rpm);

/* Evaluate all 16 layers; capacity must be at least 16. */
R6_API int r6_engine_eval_layers(const r6_engine_runtime_view *runtime,
                                 const void *esnd_data, size_t esnd_size,
                                 uint32_t sound, const r6_engine_state *state,
                                 const r6_envelope_math *math,
                                 r6_engine_layer_result *out,
                                 uint32_t capacity, uint32_t *count);

#ifdef __cplusplus
}
#endif

#endif
