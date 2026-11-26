/* nuSound2 `.nub` banks: fixed-layout header, tone table and PCM views.
 *
 * Parsers bounds-check already-read bytes and never touch files or a CRT.
 * Layouts were recovered from nuSound2_win64.dll and checked against the
 * shipped banks by tools/engine/nub_audio.py.
 */
#ifndef R6_AUDIO_H
#define R6_AUDIO_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_AUDIO_FADE_FRAME_RATE = 60,
    R6_AUDIO_STREAM_LIMIT = 0x20000000
};

/* FUN_140781ba0: integer frame delta at 60 fps, then milliseconds. */
R6_API int32_t r6_audio_fade_frames_to_ms(int32_t now_frame,
                                          int32_t max_frame);

/* FUN_180035b80: running stream-byte total, -1 past the cap. */
R6_API int64_t r6_audio_stream_reserve(int64_t total, int64_t size);

typedef struct r6_nub_header {
    uint32_t version;
    uint32_t bank_id;
    uint32_t tone_count;
    uint32_t header_size;
    uint32_t data_size;
    uint32_t first_record;
} r6_nub_header;

typedef struct r6_nub_tone {
    uint32_t index;
    uint32_t slot;
    uint32_t group;
    uint32_t record_offset;
    uint32_t length;
    uint32_t data_offset;
    uint32_t flags;
    uint32_t format_count;
    uint32_t rate;
    uint32_t channels;
    uint32_t bits;
    uint32_t loop_flag;
    float volume;
    uint32_t three_d_param_no;
    uint16_t format_tag;
    uint16_t format_channels;
    uint16_t block_align;
    uint32_t byte_rate;
} r6_nub_tone;

/* Playback control fields read from a tone record by nuSound2. */
typedef struct r6_nub_control {
    float three_d_float_a;
    float three_d_float_b;
    uint32_t three_d_param_no;
    float volume_cap;
    float pan_cap;
    uint32_t bus_id;
    uint32_t voice_bus;
} r6_nub_control;

/* Registration view used by nuSound2BankRegister (FUN_18002eb80). */
typedef struct r6_bank_setup_tone {
    uint32_t length;
    uint32_t data_offset;
    uint32_t formats;
} r6_bank_setup_tone;

typedef struct r6_bank_setup_view {
    unsigned char version[3];
    uint32_t tone_count;
    uint32_t data_offset;
    uint32_t data_size;
    uint32_t record_table;
    const r6_bank_setup_tone *tones;
} r6_bank_setup_view;

/* Parse the header and every tone record. capacity is a tone count; on
 * R6_ERR_BUFFER, header->tone_count holds the required count. */
R6_API int r6_nub_parse(const void *data, size_t size, r6_nub_header *header,
                        r6_nub_tone *tones, size_t capacity);

/* Read the control fields for a parsed tone. */
R6_API int r6_nub_tone_control(const void *data, size_t size,
                               const r6_nub_tone *tone, r6_nub_control *out);

/* Zero-copy view of the PCM bytes for a parsed tone. The caller owns `data`. */
R6_API int r6_nub_pcm(const void *data, size_t size,
                      const r6_nub_header *header, const r6_nub_tone *tone,
                      const void **out, size_t *out_size);

/* Read the bank registration view into caller-owned tone storage. On
 * R6_ERR_BUFFER, view->tone_count holds the required tone count. */
R6_API int r6_bank_setup_init(r6_bank_setup_view *view, const void *data,
                              size_t size, r6_bank_setup_tone *tones,
                              size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
