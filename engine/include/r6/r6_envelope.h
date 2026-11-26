/* Port of FUN_1407d0dc0's pitch/volume curve evaluation.
 *
 * The core stays freestanding: pow and exp2 come from host callbacks. Supplying
 * libm (or any equivalent) on the host keeps the float results identical to
 * the Python reference while the core links no CRT or libm.
 */
#ifndef R6_ENVELOPE_H
#define R6_ENVELOPE_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_ENVELOPE_VALUES 5

typedef struct r6_envelope_math {
    void *user;
    double (*pow_value)(void *user, double base, double exponent);
    double (*exp2_value)(void *user, double exponent);
} r6_envelope_math;

typedef struct r6_envelope_result {
    int32_t pitch;
    int32_t volume;
} r6_envelope_result;

/* `envelope` is the packed (start, peak, centre, fall_start, fall_end) row.
 * amplitude/volume_base/volume_scale/detune_divisor/curve_power are the values
 * the native caller takes from EMTIS and runtime state.
 */
R6_API int r6_envelope_eval(const r6_envelope_math *math,
                            const int32_t *envelope, int32_t rpm,
                            double amplitude, double volume_base,
                            double volume_scale, double detune_divisor,
                            double curve_power, r6_envelope_result *out);

#ifdef __cplusplus
}
#endif

#endif
