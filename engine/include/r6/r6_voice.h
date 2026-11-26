/* Freestanding port of the recovered 0xa0 KeyOn voice-request ABI.
 *
 * Layout and defaults come from `tools/engine/audio_events.py`
 * (FUN_1800237d0, FUN_1800011b0 and the extended-KeyOn blobs). Pointer
 * fields are stored as opaque integers: the core only copies bytes and never
 * dereferences them. No allocation, CRT, libm or audio device.
 */
#ifndef R6_VOICE_H
#define R6_VOICE_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"
#include "r6_envelope.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_VOICE_REQUEST_SIZE = 0xA0,
    R6_VOICE_EXT_A_SIZE = 0x34,
    R6_VOICE_EXT_B_SIZE = 0x1C,
    R6_VOICE_EXT_A_OFFSET = 0x34,
    R6_VOICE_EXT_B_OFFSET = 0x68,
    R6_VOICE_FLOAT_OFFSET = 0x84,
    R6_VOICE_CENTS_DIVISOR = 1200,
    R6_VOICE_CHAIN_COUNT = 0x20,
    R6_VOICE_CHAIN_STRIDE = 0xD0,
    R6_VOICE_CHAIN_FLOATS = 0x34,
    R6_VOICE_CHAIN_VOLUME = 0x00,
    R6_VOICE_CHAIN_VOLUME_DB = 0x01,
    R6_VOICE_CHAIN_PITCH_CENTS = 0x02,
    R6_VOICE_CHAIN_FX_VOLUME = 0x03,
    R6_VOICE_CHAIN_MIX_VOLUME = 0x04,
    R6_VOICE_CHAIN_FILTER_A = 0x05,
    R6_VOICE_CHAIN_FILTER_B = 0x06,
    R6_VOICE_CHAIN_SPEAKER_MATRIX = 0x07,
    R6_VOICE_CHAIN_SPEAKER_FLOATS = 0x24,
    R6_VOICE_CHAIN_RESERVED = 0x2B,
    R6_VOICE_CHAIN_MODE = 0x2C,
    R6_VOICE_CHAIN_CHANNEL = 0x2D,
    R6_VOICE_CHAIN_PARAM_A = 0x2E,
    R6_VOICE_CHAIN_PARAM_B = 0x2F,
    R6_VOICE_CHAIN_BUS = 0x30,
    R6_VOICE_CHAIN_BANK = 0x31,
    R6_VOICE_CHAIN_TONE = 0x32,
    R6_VOICE_CHAIN_VOICE = 0x33,
    R6_VOICE_CORE_FILTER_A = 0x08,
    R6_VOICE_CORE_CHANNEL = 0x14,
    R6_VOICE_CORE_VOLUME = 0x2C,
    R6_VOICE_CORE_FX_VOLUME = 0x30,
    R6_VOICE_CORE_BUS = 0x38,
    R6_VOICE_CORE_FILTER_B = 0x44,
    R6_VOICE_CORE_PITCH = 0x48,
    R6_VOICE_CORE_MIN_SIZE = 0x4C
};

typedef struct r6_voice_request {
    int32_t request;
    int32_t bank;
    int32_t bank_info;
    uint32_t tone;
    uint64_t bank_ptr;
    uint64_t tone_ptr;
    uint64_t voice_ptr;
    int32_t chain_tone;
    uint32_t extended;
    uint32_t reserved;
    unsigned char ext_a[R6_VOICE_EXT_A_SIZE];
    unsigned char ext_b[R6_VOICE_EXT_B_SIZE];
    float volume;
    float pan;
    uint32_t flags;
    float extra_a;
    float extra_b;
    float extra_c;
} r6_voice_request;

/* Zero the record, store the six recovered float defaults. */
R6_API int r6_voice_request_init(r6_voice_request *request);

/* Copy an extended-KeyOn blob into its fixed slot; oversize is rejected. */
R6_API int r6_voice_request_set_ext(r6_voice_request *request, int a,
                                    const void *data, size_t size);

/* Convert between the struct and a host-owned 0xa0-byte record. */
R6_API int r6_voice_request_pack(const r6_voice_request *request, void *data,
                                 size_t size);
R6_API int r6_voice_request_unpack(const void *data, size_t size,
                                   r6_voice_request *request);

/* One 0xd0-byte chained-voice state record: 52 f32 slots. */
typedef struct r6_voice_chain_state {
    float values[R6_VOICE_CHAIN_FLOATS];
} r6_voice_chain_state;

/* Access the 32 host-owned chained-voice records at instance +0x21c. */
R6_API int r6_voice_chain_read(const void *data, size_t size, uint32_t index,
                               r6_voice_chain_state *out);
R6_API int r6_voice_chain_write(void *data, size_t size, uint32_t index,
                                const r6_voice_chain_state *state);

/* Apply the recovered clamped volumes, cents pitch, filters, bus and channel
 * to a host-owned core voice. Speaker matrix, mode and core-voice lookup are
 * not written: their destination offsets are not established. */
R6_API int r6_voice_chain_apply(const r6_voice_chain_state *state, void *voice,
                                size_t size, const r6_envelope_math *math);

/* FUN_18001bf00/b1b0/bd30: NaN or negative -> 0, above one -> 1. */
R6_API float r6_voice_clamp_unit(float value);

/* FUN_18001be70: 2^(cents/1200), using the host pow hook. */
R6_API int r6_voice_cents_to_pitch(const r6_envelope_math *math, double cents,
                                   double *out);

/* Recovered status codes and call-site facts for extended KeyOn / 3D SE.
 * Values are copied only; no native method is called and no pointer is used. */
#define R6_VOICE_BANK_ERR_BAD_INDEX 0x8000001Eu
#define R6_VOICE_BANK_ERR_BAD_FORMAT 0x8000001Du
#define R6_VOICE_BANK_ERR_BYTE0 0x80000042u
#define R6_VOICE_BANK_ERR_NO_SLOT 0x8000001Bu
#define R6_VOICE_BANK_ERR_NULL_DATA 0x80000024u
#define R6_VOICE_BANK_ERR_ALREADY_SET 0x80000021u
#define R6_VOICE_BANK_ERR_VOICE_FAIL 0x80000026u
#define R6_VOICE_BANK_ERR_STREAM_FAIL 0x80000027u
#define R6_VOICE_3D_ERR_NULL_SECONDARY 0x80000031u
#define R6_VOICE_3D_ERR_NULL_THIRD 0x80000032u
#define R6_VOICE_3D_ERR_NULL_POSITION 0x80000033u
#define R6_VOICE_CHAIN_ERR_LAST_TONE 0x8000004Bu

typedef struct r6_voice_dispatch_facts_t {
    uint32_t bank_errors[8];
    uint32_t null_errors[3];
    uint32_t chain_error;
    uint32_t chain_modes[3];
    uint32_t ext_offsets[2];
    uint32_t ext_sizes[2];
    uint32_t game_layout[5];
    uint64_t addresses[8];
} r6_voice_dispatch_facts_t;

R6_API void r6_voice_dispatch_facts(r6_voice_dispatch_facts_t *out);

/* FUN_18001ed00 core-voice lookup table facts; instance storage stays host
 * owned and no lookup result is computed here. */
typedef struct r6_voice_core_table_facts_t {
    uint32_t count;
    uint32_t offset;
    uint32_t stride;
    uint32_t mode;
    uint64_t lookup_address;
} r6_voice_core_table_facts_t;

R6_API void r6_voice_core_table_facts(r6_voice_core_table_facts_t *out);

#ifdef __cplusplus
}
#endif

#endif
