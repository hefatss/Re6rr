/* Freestanding port of the recovered nuSound2 mixer pieces.
 *
 * Bus layout and dB calibration come from `tools/engine/audio_events.py`
 * (FUN_18001cbc0, FUN_180020290, FUN_1800201b0). The core uses only float
 * arithmetic; no libm, allocation, files or audio device.
 */
#ifndef R6_MIXER_H
#define R6_MIXER_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_MIXER_BUS_COUNT = 0x44,
    R6_MIXER_BUS_STRIDE = 0x48,
    R6_MIXER_BUS_VOLUME_OFFSET = 0x00,
    R6_MIXER_BUS_MODE_OFFSET = 0x10,
    R6_MIXER_BUS_FRAME_OFFSET = 0x14,
    R6_MIXER_BUS_TARGET_OFFSET = 0x18,
    R6_MIXER_BUS_STEP_OFFSET = 0x1C,
    R6_MIXER_FADE_MODE = 0x02,
    R6_MIXER_INVALID_BUS = 0x80000001
};

typedef struct r6_mixer_bus {
    float volume;
    float target;
    float step;
    uint32_t frames;
    uint32_t mode;
} r6_mixer_bus;

/* Read/write one 0x48-byte bus from a host-owned bus array. */
R6_API int r6_mixer_bus_read(const void *data, size_t size, uint32_t index,
                             r6_mixer_bus *out);
R6_API int r6_mixer_bus_write(void *data, size_t size, uint32_t index,
                              const r6_mixer_bus *bus);

/* Direct port of nuSound2BusFade: frames < 1 sets immediately. */
R6_API int r6_mixer_bus_fade(r6_mixer_bus *bus, float target, uint32_t frames);

/* Piecewise-linear dB conversions, caller supplies runtime calibration. */
R6_API int r6_mixer_db_to_volume(float db, float lo, float mid, float hi,
                                 float *out);
R6_API int r6_mixer_volume_to_db(float volume, float lo, float mid, float hi,
                                 float *out);

#ifdef __cplusplus
}
#endif

#endif
