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

int r6_voice_chain_apply(const r6_voice_chain_state *state, void *voice,
                         size_t size, const r6_envelope_math *math) {
    unsigned char *at = (unsigned char *)voice;
    double pitch = 0.0;
    int rc;
    if (!state || !at || !math || size < R6_VOICE_CORE_MIN_SIZE) {
        return R6_ERR_ARG;
    }
    rc = r6_voice_cents_to_pitch(
        math, (double)state->values[R6_VOICE_CHAIN_PITCH_CENTS], &pitch);
    if (rc != R6_OK) {
        return rc;
    }
    voice_put_f32(at + R6_VOICE_CORE_VOLUME,
                  r6_voice_clamp_unit(state->values[R6_VOICE_CHAIN_VOLUME]));
    voice_put_f32(at + R6_VOICE_CORE_FX_VOLUME,
                  r6_voice_clamp_unit(state->values[R6_VOICE_CHAIN_FX_VOLUME]));
    voice_put_f32(at + R6_VOICE_CORE_PITCH, (float)pitch);
    voice_put_f32(at + R6_VOICE_CORE_FILTER_A,
                  r6_voice_clamp_unit(state->values[R6_VOICE_CHAIN_FILTER_A]));
    voice_put_f32(at + R6_VOICE_CORE_FILTER_B,
                  r6_voice_clamp_unit(state->values[R6_VOICE_CHAIN_FILTER_B]));
    voice_put_u32(at + R6_VOICE_CORE_BUS,
                  (uint32_t)state->values[R6_VOICE_CHAIN_BUS]);
    voice_put_u32(at + R6_VOICE_CORE_CHANNEL,
                  (uint32_t)state->values[R6_VOICE_CHAIN_CHANNEL]);
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

void r6_voice_dispatch_facts(r6_voice_dispatch_facts_t *out) {
    if (!out) {
        return;
    }
    r6_memset(out, 0, sizeof(*out));
    out->bank_errors[0] = R6_VOICE_BANK_ERR_BAD_INDEX;
    out->bank_errors[1] = R6_VOICE_BANK_ERR_BAD_FORMAT;
    out->bank_errors[2] = R6_VOICE_BANK_ERR_BYTE0;
    out->bank_errors[3] = R6_VOICE_BANK_ERR_NO_SLOT;
    out->bank_errors[4] = R6_VOICE_BANK_ERR_NULL_DATA;
    out->bank_errors[5] = R6_VOICE_BANK_ERR_ALREADY_SET;
    out->bank_errors[6] = R6_VOICE_BANK_ERR_VOICE_FAIL;
    out->bank_errors[7] = R6_VOICE_BANK_ERR_STREAM_FAIL;
    out->null_errors[0] = R6_VOICE_3D_ERR_NULL_SECONDARY;
    out->null_errors[1] = R6_VOICE_3D_ERR_NULL_THIRD;
    out->null_errors[2] = R6_VOICE_3D_ERR_NULL_POSITION;
    out->chain_error = R6_VOICE_CHAIN_ERR_LAST_TONE;
    out->chain_modes[0] = 1u;
    out->chain_modes[1] = 2u;
    out->chain_modes[2] = 3u;
    out->ext_offsets[0] = R6_VOICE_EXT_A_OFFSET;
    out->ext_offsets[1] = R6_VOICE_EXT_B_OFFSET;
    out->ext_sizes[0] = R6_VOICE_EXT_A_SIZE;
    out->ext_sizes[1] = R6_VOICE_EXT_B_SIZE;
    out->game_layout[0] = 0x60u;
    out->game_layout[1] = 2u;
    out->game_layout[2] = 0x0Cu;
    out->game_layout[3] = 0x1Cu;
    out->game_layout[4] = 8u;
    out->addresses[0] = 0x18001A4E0ull;
    out->addresses[1] = 0x1800237D0ull;
    out->addresses[2] = 0x180026A60ull;
    out->addresses[3] = 0x1800363B0ull;
    out->addresses[4] = 0x1800361F0ull;
    out->addresses[5] = 0x180034E70ull;
    out->addresses[6] = 0x140C50D80ull;
    out->addresses[7] = 0x140DEE20Aull;
}

void r6_voice_keyon_users(r6_voice_keyon_users_t *out) {
    if (!out) {
        return;
    }
    r6_memset(out, 0, sizeof(*out));
    out->plain[0] = 0x18002A380ull;
    out->plain[1] = 0x18002A650ull;
    out->plain[2] = 0x18002A410ull;
    out->plain[3] = 0x18002A6E0ull;
    out->plain[4] = 0x180029E00ull;
    out->plain[5] = 0x18002A490ull;
    out->point[0] = 0x1800363B0ull;
    out->point[1] = 0x1800361F0ull;
    out->point[2] = 0x180036900ull;
    out->point[3] = 0x180036740ull;
    out->point[4] = 0x180029CC0ull;
    out->point[5] = 0x180029EB0ull;
    out->line[0] = 0x1800365E0ull;
    out->line[1] = 0x180036A10ull;
    out->extended[0] = 0u;
    out->extended[1] = 1u;
    out->extended[2] = 1u;
    out->position_floats[0] = 0u;
    out->position_floats[1] = 3u;
    out->position_floats[2] = 4u;
    out->secondary_bytes = 0x0Cu;
}

void r6_voice_core_table_facts(r6_voice_core_table_facts_t *out) {
    if (!out) {
        return;
    }
    r6_memset(out, 0, sizeof(*out));
    out->count = 0xC0u;
    out->offset = 0x44u;
    out->stride = 0x178u;
    out->mode = 7u;
    out->lookup_address = 0x18001ED00ull;
}
