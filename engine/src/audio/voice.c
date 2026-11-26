/* Bounds-checked KeyOn request builder and recovered chain arithmetic. */

#include "core/internal.h"
#include "r6/r6_voice.h"

static uint32_t voice_u32(const unsigned char *at) {
    return (uint32_t)at[0] | ((uint32_t)at[1] << 8) |
           ((uint32_t)at[2] << 16) | ((uint32_t)at[3] << 24);
}

static void voice_put_u32(unsigned char *at, uint32_t value) {
    at[0] = (unsigned char)value;
    at[1] = (unsigned char)(value >> 8);
    at[2] = (unsigned char)(value >> 16);
    at[3] = (unsigned char)(value >> 24);
}

static uint64_t voice_u64(const unsigned char *at) {
    return (uint64_t)voice_u32(at) | ((uint64_t)voice_u32(at + 4) << 32);
}

static void voice_put_u64(unsigned char *at, uint64_t value) {
    voice_put_u32(at, (uint32_t)value);
    voice_put_u32(at + 4, (uint32_t)(value >> 32));
}

static float voice_f32(const unsigned char *at) {
    union {
        uint32_t u;
        float f;
    } bits;
    bits.u = voice_u32(at);
    return bits.f;
}

static void voice_put_f32(unsigned char *at, float value) {
    union {
        float f;
        uint32_t u;
    } bits;
    bits.f = value;
    voice_put_u32(at, bits.u);
}

int r6_voice_request_init(r6_voice_request *request) {
    if (!request) {
        return R6_ERR_ARG;
    }
    r6_memset(request, 0, sizeof(*request));
    request->chain_tone = -1;
    request->volume = 1.0f;
    request->extra_b = 1.0f;
    request->extra_c = 1.0f;
    return R6_OK;
}

int r6_voice_request_set_ext(r6_voice_request *request, int a,
                             const void *data, size_t size) {
    unsigned char *slot;
    size_t capacity;
    if (!request) {
        return R6_ERR_ARG;
    }
    slot = a ? request->ext_b : request->ext_a;
    capacity = (size_t)(a ? R6_VOICE_EXT_B_SIZE : R6_VOICE_EXT_A_SIZE);
    if (size > capacity || (!data && size != 0)) {
        return R6_ERR_BUFFER;
    }
    if (size) {
        r6_memcpy(slot, data, size);
    } else {
        r6_memset(slot, 0, capacity);
    }
    return R6_OK;
}

int r6_voice_request_pack(const r6_voice_request *request, void *data,
                          size_t size) {
    unsigned char *at = (unsigned char *)data;
    if (!request || !at || size < R6_VOICE_REQUEST_SIZE) {
        return R6_ERR_ARG;
    }
    r6_memset(at, 0, R6_VOICE_REQUEST_SIZE);
    voice_put_u32(at + 0x00, (uint32_t)request->request);
    voice_put_u32(at + 0x04, (uint32_t)request->bank);
    voice_put_u32(at + 0x08, request->bank_info);
    voice_put_u32(at + 0x0C, request->tone);
    voice_put_u64(at + 0x10, request->bank_ptr);
    voice_put_u64(at + 0x18, request->tone_ptr);
    voice_put_u64(at + 0x20, request->voice_ptr);
    voice_put_u32(at + 0x28, (uint32_t)request->chain_tone);
    voice_put_u32(at + 0x2C, request->extended);
    voice_put_u32(at + 0x30, request->reserved);
    r6_memcpy(at + R6_VOICE_EXT_A_OFFSET, request->ext_a,
              R6_VOICE_EXT_A_SIZE);
    r6_memcpy(at + R6_VOICE_EXT_B_OFFSET, request->ext_b,
              R6_VOICE_EXT_B_SIZE);
    voice_put_f32(at + 0x84, request->volume);
    voice_put_f32(at + 0x88, request->pan);
    voice_put_u32(at + 0x8C, request->flags);
    voice_put_f32(at + 0x90, request->extra_a);
    voice_put_f32(at + 0x94, request->extra_b);
    voice_put_f32(at + 0x98, request->extra_c);
    return R6_OK;
}

int r6_voice_request_unpack(const void *data, size_t size,
                            r6_voice_request *request) {
    const unsigned char *at = (const unsigned char *)data;
    if (!request || !at || size < R6_VOICE_REQUEST_SIZE) {
        return R6_ERR_ARG;
    }
    r6_memset(request, 0, sizeof(*request));
    request->request = (int32_t)voice_u32(at + 0x00);
    request->bank = (int32_t)voice_u32(at + 0x04);
    request->bank_info = (int32_t)voice_u32(at + 0x08);
    request->tone = voice_u32(at + 0x0C);
    request->bank_ptr = voice_u64(at + 0x10);
    request->tone_ptr = voice_u64(at + 0x18);
    request->voice_ptr = voice_u64(at + 0x20);
    request->chain_tone = (int32_t)voice_u32(at + 0x28);
    request->extended = voice_u32(at + 0x2C);
    request->reserved = voice_u32(at + 0x30);
    r6_memcpy(request->ext_a, at + R6_VOICE_EXT_A_OFFSET,
              R6_VOICE_EXT_A_SIZE);
    r6_memcpy(request->ext_b, at + R6_VOICE_EXT_B_OFFSET,
              R6_VOICE_EXT_B_SIZE);
    request->volume = voice_f32(at + 0x84);
    request->pan = voice_f32(at + 0x88);
    request->flags = voice_u32(at + 0x8C);
    request->extra_a = voice_f32(at + 0x90);
    request->extra_b = voice_f32(at + 0x94);
    request->extra_c = voice_f32(at + 0x98);
    return R6_OK;
}

int r6_voice_chain_read(const void *data, size_t size, uint32_t index,
                        r6_voice_chain_state *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t i;
    if (!bytes || !out || index >= R6_VOICE_CHAIN_COUNT ||
        size < (size_t)R6_VOICE_CHAIN_COUNT * R6_VOICE_CHAIN_STRIDE) {
        return R6_ERR_ARG;
    }
    bytes += (size_t)index * R6_VOICE_CHAIN_STRIDE;
    for (i = 0; i < R6_VOICE_CHAIN_FLOATS; i++) {
        out->values[i] = voice_f32(bytes + (size_t)i * 4u);
    }
    return R6_OK;
}

int r6_voice_chain_write(void *data, size_t size, uint32_t index,
                         const r6_voice_chain_state *state) {
    unsigned char *bytes = (unsigned char *)data;
    uint32_t i;
    if (!bytes || !state || index >= R6_VOICE_CHAIN_COUNT ||
        size < (size_t)R6_VOICE_CHAIN_COUNT * R6_VOICE_CHAIN_STRIDE) {
        return R6_ERR_ARG;
    }
    bytes += (size_t)index * R6_VOICE_CHAIN_STRIDE;
    for (i = 0; i < R6_VOICE_CHAIN_FLOATS; i++) {
        voice_put_f32(bytes + (size_t)i * 4u, state->values[i]);
    }
    return R6_OK;
}

float r6_voice_clamp_unit(float value) {
    if (value != value || value < 0.0f) {
        return 0.0f;
    }
    return value > 1.0f ? 1.0f : value;
}

int r6_voice_cents_to_pitch(const r6_envelope_math *math, double cents,
                            double *out) {
    if (!math || !math->pow_value || !out) {
        return R6_ERR_ARG;
    }
    *out = math->pow_value(math->user, 2.0,
                           cents / (double)R6_VOICE_CENTS_DIVISOR);
    return R6_OK;
}
