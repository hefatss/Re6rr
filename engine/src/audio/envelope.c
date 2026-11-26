/* Pitch/volume curve evaluation with host-supplied pow and exp2. */

#include "r6/r6_envelope.h"

static int32_t envelope_i32(double value) {
    if (value >= 2147483647.0) {
        return 2147483647;
    }
    if (value <= -2147483648.0) {
        return -2147483648;
    }
    return (int32_t)value;
}

int r6_envelope_eval(const r6_envelope_math *math, const int32_t *envelope,
                     int32_t rpm, double amplitude, double volume_base,
                     double volume_scale, double detune_divisor,
                     double curve_power, r6_envelope_result *out) {
    int32_t start;
    int32_t peak;
    int32_t centre;
    int32_t fall_start;
    int32_t fall_end;
    double level;
    double detune;
    if (!math || !math->pow_value || !math->exp2_value || !envelope || !out ||
        detune_divisor == 0.0) {
        return R6_ERR_ARG;
    }
    start = envelope[0];
    peak = envelope[1];
    centre = envelope[2];
    fall_start = envelope[3];
    fall_end = envelope[4];
    if (rpm < start) {
        level = 0.0;
    } else if (rpm < peak) {
        level = (double)(rpm - start) / (double)(peak - start);
    } else if (fall_start < rpm) {
        level = rpm < fall_end
            ? (double)(rpm - fall_end) / (double)(fall_start - fall_end)
            : 0.0;
    } else {
        level = 1.0;
    }
    out->pitch = level > 0.0
        ? envelope_i32(math->pow_value(math->user, level, curve_power) *
                       amplitude)
        : 0;
    detune = (double)(rpm - centre) * volume_scale / detune_divisor;
    out->volume = envelope_i32(
        math->exp2_value(math->user, detune) * volume_base);
    return R6_OK;
}
