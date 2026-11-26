/* Bounds-checked R6ERS reader and the recovered 16-layer state evaluator. */

#include "core/internal.h"
#include "r6/r6_engine_runtime.h"
#include "r6/r6_engine_sound.h"

static const unsigned char runtime_magic[8] = {
    'R', '6', 'E', 'R', 'S', 0, 1, 0
};

static uint64_t runtime_u64(const unsigned char *at) {
    uint64_t value = 0;
    uint32_t i;
    for (i = 0; i < 8; i++) {
        value |= (uint64_t)at[i] << (i * 8);
    }
    return value;
}

static double runtime_f64(const unsigned char *at) {
    union {
        uint64_t u;
        double d;
    } bits;
    bits.u = runtime_u64(at);
    return bits.d;
}

static double runtime_max(double a, double b) {
    return a > b ? a : b;
}

static int32_t runtime_i32(double value) {
    if (value >= 2147483647.0) {
        return 2147483647;
    }
    if (value <= -2147483648.0) {
        return -2147483648;
    }
    return (int32_t)value;
}

static double runtime_volume(double value) {
    if (value >= 1.0) {
        return 0.0;
    }
    return value < -10000.0 ? -10000.0 : value;
}

int r6_engine_runtime_init(r6_engine_runtime_view *view, const void *data,
                           size_t size) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t sound_count;
    uint32_t header_count;
    uint32_t constant_count;
    uint64_t header_off;
    uint64_t constants_off;
    uint64_t expected;
    if (!view || !bytes || size < R6_ENGINE_RUNTIME_HEADER_SIZE ||
        r6_memcmp(bytes, runtime_magic, sizeof(runtime_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u || r6_u32(bytes, 24) != 0u ||
        r6_u32(bytes, 28) != 0u) {
        return R6_ERR_FORMAT;
    }
    sound_count = r6_u32(bytes, 12);
    header_count = r6_u32(bytes, 16);
    constant_count = r6_u32(bytes, 20);
    header_off = R6_ENGINE_RUNTIME_HEADER_SIZE +
                 (uint64_t)sound_count * R6_ENGINE_RUNTIME_SOUND_SIZE;
    constants_off = header_off + (uint64_t)header_count * 8u;
    expected = constants_off + (uint64_t)constant_count * 8u;
    if (sound_count == 0 || header_count < 12 || constant_count < 20 ||
        expected != size) {
        return R6_ERR_FORMAT;
    }
    view->data = bytes;
    view->size = size;
    view->sound_count = sound_count;
    view->header_count = header_count;
    view->constant_count = constant_count;
    view->sounds_off = R6_ENGINE_RUNTIME_HEADER_SIZE;
    view->header_off = (uint32_t)header_off;
    view->constants_off = (uint32_t)constants_off;
    return R6_OK;
}

int r6_engine_runtime_sound(const r6_engine_runtime_view *view,
                            uint32_t sound, double *lexical8,
                            double *lexical13) {
    const unsigned char *at;
    if (!view || !lexical8 || !lexical13 || sound >= view->sound_count) {
        return R6_ERR_ARG;
    }
    at = view->data + view->sounds_off +
         (size_t)sound * R6_ENGINE_RUNTIME_SOUND_SIZE;
    if (r6_u16(at, 0) != sound || r6_u16(at, 2) != 0u) {
        return R6_ERR_FORMAT;
    }
    *lexical8 = runtime_f64(at + 4);
    *lexical13 = runtime_f64(at + 12);
    return R6_OK;
}

int r6_engine_runtime_header(const r6_engine_runtime_view *view,
                             uint32_t index, double *out) {
    if (!view || !out || index >= view->header_count) {
        return R6_ERR_ARG;
    }
    *out = runtime_f64(view->data + view->header_off + (size_t)index * 8u);
    return R6_OK;
}

int r6_engine_runtime_constant(const r6_engine_runtime_view *view,
                               uint32_t index, double *out) {
    if (!view || !out || index >= view->constant_count) {
        return R6_ERR_ARG;
    }
    *out = runtime_f64(view->data + view->constants_off +
                       (size_t)index * 8u);
    return R6_OK;
}

int r6_engine_state_init(r6_engine_state *state, int32_t rpm) {
    uint32_t i;
    if (!state) {
        return R6_ERR_ARG;
    }
    r6_memset(state, 0, sizeof(*state));
    state->rpm = rpm;
    state->current = rpm;
    state->curve_scale = 1.0;
    for (i = 0; i < R6_ENGINE_LAYER_COUNT; i++) {
        state->layer_base[i] = 1.0;
    }
    return R6_OK;
}

int r6_engine_eval_layers(const r6_engine_runtime_view *runtime,
                          const void *esnd_data, size_t esnd_size,
                          uint32_t sound, const r6_engine_state *state,
                          const r6_envelope_math *math,
                          r6_engine_layer_result *out, uint32_t capacity,
                          uint32_t *count) {
    r6_esnd_layer layer;
    r6_envelope_result env;
    double lex8 = 0.0;
    double lex13 = 0.0;
    double header[12];
    double constants[13];
    double f34;
    double f4f;
    double f20;
    double f134;
    double f2d;
    double smoothed[3];
    double boost;
    int32_t rpm_value;
    int32_t adjusted;
    uint32_t i;
    int rc;

    if (!runtime || !esnd_data || !state || !math || !out || !count ||
        capacity < R6_ENGINE_LAYER_COUNT) {
        return R6_ERR_ARG;
    }
    if (r6_engine_runtime_sound(runtime, sound, &lex8, &lex13) != R6_OK) {
        return R6_ERR_ARG;
    }
    for (i = 0; i < 12; i++) {
        if (r6_engine_runtime_header(runtime, i, &header[i]) != R6_OK) {
            return R6_ERR_ARG;
        }
    }
    for (i = 0; i <= R6_ENGINE_CONST_BOOST_LIMIT; i++) {
        if (r6_engine_runtime_constant(runtime, i, &constants[i]) != R6_OK) {
            return R6_ERR_ARG;
        }
    }
    if (header[0] == 0.0 || header[6] == 0.0 || header[11] == 0.0 ||
        constants[R6_ENGINE_CONST_REQUEST_AMPLITUDE] == 0.0 ||
        constants[R6_ENGINE_CONST_STATE_THRESHOLD] == 0.0 ||
        constants[R6_ENGINE_CONST_BOOST_LIMIT] == 0.0) {
        return R6_ERR_ARG;
    }

    rpm_value = state->rpm;
    adjusted = rpm_value + state->request_offset;
    f34 = runtime_max(lex13, state->smooth34);
    f4f = state->smooth4f;
    f20 = runtime_max(lex8, state->smooth20);
    f134 = state->f134;
    f2d = state->f2d;
    if (f34 == 0.0) {
        return R6_ERR_ARG;
    }
    if (!state->flag) {
        smoothed[0] = f20;
        smoothed[1] = f134;
        smoothed[2] = f2d;
        for (i = 0; i < 3; i++) {
            double value = (state->floors[i][1] + state->floors[i][0] -
                            state->floors[i][2]) * state->throttle +
                           state->floors[i][2];
            if (value > smoothed[i]) {
                smoothed[i] = value;
            }
        }
        f20 = smoothed[0];
        f134 = smoothed[1];
        f2d = smoothed[2];
    }
    if (state->current < constants[R6_ENGINE_CONST_STATE_THRESHOLD]) {
        boost = ((constants[R6_ENGINE_CONST_STATE_THRESHOLD] - state->current) /
                 constants[R6_ENGINE_CONST_STATE_THRESHOLD]) *
                (1.0 - constants[R6_ENGINE_CONST_STATE_MIN_SCALE]) +
                constants[R6_ENGINE_CONST_STATE_MIN_SCALE];
    } else {
        boost = constants[R6_ENGINE_CONST_STATE_MIN_SCALE];
    }

    for (i = 0; i < R6_ENGINE_LAYER_COUNT; i++) {
        int32_t layer_rpm;
        int32_t level;
        double amplitude;
        double scale_volume;
        double factor;
        double ceiling;
        double rpm_scale;
        double raw_volume;
        uint32_t slot;

        rc = r6_esnd_get_layer(esnd_data, esnd_size, (uint16_t)sound, i,
                               &layer);
        if (rc != R6_OK) {
            return rc;
        }
        switch (layer.source) {
        case R6_ENGINE_SOURCE_A:
            layer_rpm = adjusted;
            amplitude = 1.0;
            scale_volume = 1.0;
            factor = 1.0;
            ceiling = header[1];
            rpm_scale = boost;
            slot = 0;
            break;
        case R6_ENGINE_SOURCE_B:
            layer_rpm = adjusted;
            amplitude = header[3];
            scale_volume = 1.0;
            factor = (f20 + f4f) / f34;
            ceiling = header[3];
            rpm_scale = boost;
            slot = 1;
            break;
        case R6_ENGINE_SOURCE_D:
            layer_rpm = rpm_value;
            amplitude = header[4];
            scale_volume = 1.0;
            factor = 1.0;
            ceiling = header[4];
            rpm_scale = 1.0;
            slot = 2;
            break;
        case R6_ENGINE_SOURCE_F:
            layer_rpm = rpm_value;
            amplitude = header[6];
            scale_volume = header[7];
            factor = f134 / header[6];
            ceiling = header[6];
            rpm_scale = 1.0;
            slot = 3;
            break;
        case R6_ENGINE_SOURCE_H:
            layer_rpm = rpm_value;
            amplitude = constants[R6_ENGINE_CONST_REQUEST_AMPLITUDE];
            scale_volume = 1.0;
            factor = f2d / constants[R6_ENGINE_CONST_REQUEST_AMPLITUDE];
            ceiling = constants[R6_ENGINE_CONST_REQUEST_AMPLITUDE];
            rpm_scale = 1.0;
            slot = 4;
            break;
        default:
            return R6_ERR_FORMAT;
        }

        rc = r6_envelope_eval(math, layer.envelope, layer_rpm, amplitude,
                              state->layer_base[i], scale_volume, header[0],
                              header[2], &env);
        if (rc != R6_OK) {
            return rc;
        }
        {
            double value = (double)env.pitch * factor;
            if (layer.source == R6_ENGINE_SOURCE_A) {
                value += f34 + f4f;
            }
            if ((layer.flags & R6_ESND_HAS_RPM) && layer.rpm_limit != 0 &&
                layer_rpm < layer.rpm_limit) {
                value *= ((double)layer_rpm / layer.rpm_limit) *
                         (1.0 - (double)layer.scale) + layer.scale;
            }
            level = runtime_i32(value * rpm_scale);
        }
        if (layer.source == R6_ENGINE_SOURCE_B) {
            level -= runtime_i32(state->sub);
        } else if (layer.source == R6_ENGINE_SOURCE_D) {
            double scale = constants[R6_ENGINE_CONST_REQUEST_PITCH];
            if (state->current < header[11]) {
                scale = ((header[11] - state->current) / header[11]) *
                        (1.0 - scale) + scale;
            }
            level = runtime_i32((double)level * scale);
        } else if (layer.source == R6_ENGINE_SOURCE_F) {
            double scale = header[9];
            if (state->current < constants[R6_ENGINE_CONST_BOOST_LIMIT]) {
                scale = ((constants[R6_ENGINE_CONST_BOOST_LIMIT] -
                          state->current) /
                         constants[R6_ENGINE_CONST_BOOST_LIMIT]) *
                        (1.0 - scale) + scale;
            }
            level = runtime_i32((double)level * scale);
        } else if (layer.source == R6_ENGINE_SOURCE_H) {
            level = runtime_i32((double)level * state->curve_scale);
        }

        raw_volume = layer.base + state->base[slot] - ceiling + (double)level;
        out[i].layer = layer.layer;
        out[i].source = layer.source;
        out[i].tone = layer.tone;
        out[i].pitch = env.pitch;
        out[i].level = level;
        out[i].volume = runtime_volume(raw_volume);
    }
    *count = R6_ENGINE_LAYER_COUNT;
    return R6_OK;
}
