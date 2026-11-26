/* Bounds-checked mixer bus access and recovered dB/fade arithmetic. */

#include "r6/r6_mixer.h"

#include "core/internal.h"

static uint32_t mixer_get_u32(const unsigned char *at) {
    return (uint32_t)at[0] | ((uint32_t)at[1] << 8) |
           ((uint32_t)at[2] << 16) | ((uint32_t)at[3] << 24);
}

static void mixer_put_u32(unsigned char *at, uint32_t value) {
    at[0] = (unsigned char)value;
    at[1] = (unsigned char)(value >> 8);
    at[2] = (unsigned char)(value >> 16);
    at[3] = (unsigned char)(value >> 24);
}

static float mixer_get_f32(const unsigned char *at) {
    union {
        uint32_t u;
        float f;
    } bits;
    bits.u = mixer_get_u32(at);
    return bits.f;
}

static void mixer_put_f32(unsigned char *at, float value) {
    union {
        float f;
        uint32_t u;
    } bits;
    bits.f = value;
    mixer_put_u32(at, bits.u);
}

static int mixer_calibration_ok(float lo, float mid, float hi) {
    return mid > lo && mid != 0.0f && hi > 1.0f;
}

int r6_mixer_bus_read(const void *data, size_t size, uint32_t index,
                      r6_mixer_bus *out) {
    const unsigned char *at = (const unsigned char *)data;
    if (!out || !at || index >= R6_MIXER_BUS_COUNT ||
        size < (size_t)R6_MIXER_BUS_COUNT * R6_MIXER_BUS_STRIDE) {
        return R6_ERR_ARG;
    }
    at += (size_t)index * R6_MIXER_BUS_STRIDE;
    out->volume = mixer_get_f32(at + R6_MIXER_BUS_VOLUME_OFFSET);
    out->mode = mixer_get_u32(at + R6_MIXER_BUS_MODE_OFFSET);
    out->frames = mixer_get_u32(at + R6_MIXER_BUS_FRAME_OFFSET);
    out->target = mixer_get_f32(at + R6_MIXER_BUS_TARGET_OFFSET);
    out->step = mixer_get_f32(at + R6_MIXER_BUS_STEP_OFFSET);
    return R6_OK;
}

int r6_mixer_bus_write(void *data, size_t size, uint32_t index,
                       const r6_mixer_bus *bus) {
    unsigned char *at = (unsigned char *)data;
    if (!bus || !at || index >= R6_MIXER_BUS_COUNT ||
        size < (size_t)R6_MIXER_BUS_COUNT * R6_MIXER_BUS_STRIDE) {
        return R6_ERR_ARG;
    }
    at += (size_t)index * R6_MIXER_BUS_STRIDE;
    mixer_put_f32(at + R6_MIXER_BUS_VOLUME_OFFSET, bus->volume);
    mixer_put_u32(at + R6_MIXER_BUS_MODE_OFFSET, bus->mode);
    mixer_put_u32(at + R6_MIXER_BUS_FRAME_OFFSET, bus->frames);
    mixer_put_f32(at + R6_MIXER_BUS_TARGET_OFFSET, bus->target);
    mixer_put_f32(at + R6_MIXER_BUS_STEP_OFFSET, bus->step);
    return R6_OK;
}

int r6_mixer_bus_fade(r6_mixer_bus *bus, float target, uint32_t frames) {
    if (!bus) {
        return R6_ERR_ARG;
    }
    if (frames < 1u) {
        bus->volume = target;
        bus->step = 0.0f;
        bus->mode = 0;
        bus->frames = 0;
    } else {
        bus->target = target;
        bus->step = (target - bus->volume) / (float)frames;
        bus->frames = frames;
        bus->mode = R6_MIXER_FADE_MODE;
    }
    return R6_OK;
}

int r6_mixer_db_to_volume(float db, float lo, float mid, float hi,
                          float *out) {
    if (!out || !mixer_calibration_ok(lo, mid, hi)) {
        return R6_ERR_ARG;
    }
    if (db <= lo) {
        *out = 0.0f;
    } else if (db < mid) {
        *out = hi / (mid - lo) * (db - lo);
    } else {
        *out = (hi - 1.0f) / mid * db + 1.0f;
    }
    return R6_OK;
}

int r6_mixer_volume_to_db(float volume, float lo, float mid, float hi,
                          float *out) {
    if (!out || !mixer_calibration_ok(lo, mid, hi)) {
        return R6_ERR_ARG;
    }
    if (volume <= 0.0f) {
        *out = lo;
    } else if (volume <= hi) {
        *out = (mid - lo) / hi * volume + lo;
    } else {
        *out = mid / (hi - 1.0f) * (volume - 1.0f);
    }
    return R6_OK;
}
