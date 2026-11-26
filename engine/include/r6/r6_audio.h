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

/* sys::Sound::Initialize config written at 0x1407d674d and validated by the
 * Impl ctor 0x140c533c0. Pointer slots are copied as opaque values. */
enum {
    R6_SOUND_CONFIG_SIZE = 0x28,
    R6_SOUND_BANK_MAX = 0x10,
    R6_SOUND_REQUEST_MAX = 0x100,
    R6_SOUND_STREAM_MIN = 1,
    R6_SOUND_STREAM_MAX = 0x10,
    R6_SOUND_CONFIG_BIN_OFFSET = 0x10,
    R6_SOUND_CONFIG_3D_OFFSET = 0x18,
    R6_SOUND_CORE_INIT_OFFSET = 0x20,
    R6_SOUND_IMPL_SIZE = 0x98,
    R6_SOUND_BANK_STRIDE = 0x20,
    R6_SOUND_REQUEST_STRIDE = 0x08,
    R6_SOUND_STREAM_STRIDE = 0x10
};

typedef struct r6_sound_init {
    uint32_t bank_num;
    uint32_t reqid_num;
    uint32_t stream_num;
    uint64_t pointers[3];
    uint32_t bank_bytes;
    uint32_t request_bytes;
    uint32_t stream_bytes;
} r6_sound_init;

/* Validate the 0x28-byte config and report the three Impl vector sizes. */
R6_API int r6_sound_init_parse(const void *data, size_t size,
                               r6_sound_init *out);

/* sys::Sound::Impl dispatch arrays: bank slots, 8-byte SE loop records and
 * 0x24-byte positional SE records. The handle is an opaque 32-bit value at
 * +0x18; the ready state sits at +0x1c, so the two do not overlap. */
enum {
    R6_SOUND_BANK_HANDLE_OFFSET = 0x18,
    R6_SOUND_BANK_STATE_OFFSET = 0x1C,
    R6_SOUND_BANK_STATE_READY = 3,
    R6_SOUND_REQUEST_COUNT = 0x22,
    R6_SOUND_LOOP_SLOT_SCENE = 0x21,
    R6_SOUND_LOOP_STRIDE = 0x08,
    R6_SOUND_POSITIONAL_STRIDE = 0x24,
    R6_SOUND_POSITIONAL_TONE_DISABLE = -1
};

typedef struct r6_sound_bank_slot {
    uint32_t handle;
    uint32_t state;
    int ready;
} r6_sound_bank_slot_t;

typedef struct r6_sound_loop_record {
    uint32_t flag;
    uint32_t tone;
} r6_sound_loop_record_t;

typedef struct r6_sound_positional_record {
    uint32_t bank;
    int32_t tone;
    int32_t frames;
    float x;
    float y;
    float z;
} r6_sound_positional_record_t;

R6_API int r6_sound_bank_slot(const void *data, size_t size, uint32_t index,
                              r6_sound_bank_slot_t *out);
R6_API int r6_sound_loop_record(const void *data, size_t size, uint32_t index,
                                r6_sound_loop_record_t *out);
R6_API int r6_sound_positional_record(const void *data, size_t size,
                                      uint32_t index,
                                      r6_sound_positional_record_t *out);

/* Header of data/sound/config.bin: six (count, offset) pairs after 0x18,
 * with the float block offset at 0x14. Section payloads stay in the blob. */
enum {
    R6_SOUND_BIN_HEADER_SIZE = 0x50,
    R6_SOUND_BIN_SECTIONS = 6,
    R6_SOUND_BIN_FLOAT_OFFSET = 0x14,
    R6_SOUND_BIN_PAIRS_OFFSET = 0x18
};

typedef struct r6_sound_bin {
    uint32_t size;
    uint32_t header_size;
    uint32_t float_offset;
    uint32_t counts[R6_SOUND_BIN_SECTIONS];
    uint32_t offsets[R6_SOUND_BIN_SECTIONS];
} r6_sound_bin;

R6_API int r6_sound_bin_parse(const void *data, size_t size,
                              r6_sound_bin *out);

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

/* nuSound2BankRegister slot scan (FUN_18002f1c0): the first slot whose
 * pointer at slot*0x804+0x42 is null. The table stays caller-owned. */
enum {
    R6_BANK_SLOT_COUNT = 0x40,
    R6_BANK_SLOT_STRIDE = 0x804,
    R6_BANK_SLOT_POINTER_OFFSET = 0x42,
    R6_BANK_SLOT_TABLE_SIZE = 0x20100,
    R6_BANK_NO_SLOT = 0x8000001B
};

R6_API int r6_bank_slot_find(const void *slots, size_t size, uint32_t *out);

/* nuSound2BankStr.bin and nuSound2ToneStr<BANK>.bin. Names and WAV paths are
 * copied into fixed NUL-padded fields; the blob itself stays caller-owned. */
enum {
    R6_SOUND_STRINGS_BANK = 0,
    R6_SOUND_STRINGS_TONE = 1,
    R6_SOUND_STRINGS_HEADER_SIZE = 0x20,
    R6_SOUND_STRINGS_FIELD_SIZE = 0x40,
    R6_SOUND_STRINGS_BANK_ROW_SIZE = 0x30,
    R6_SOUND_STRINGS_TONE_ROW_SIZE = 0x80,
    R6_SOUND_STRINGS_TONE_ROWS_OFFSET = 0x40
};

typedef struct r6_sound_strings_header {
    uint32_t version;
    uint32_t bank_id;
    uint32_t count;
    uint32_t size;
    uint32_t name_size;
    uint32_t path_size;
    uint32_t rows_off;
    uint32_t row_size;
} r6_sound_strings_header;

typedef struct r6_sound_strings_row_t {
    char name[R6_SOUND_STRINGS_FIELD_SIZE];
    char value[R6_SOUND_STRINGS_FIELD_SIZE];
    uint32_t id;
} r6_sound_strings_row_t;

R6_API int r6_sound_strings_parse(const void *data, size_t size, int kind,
                                  r6_sound_strings_header *out);

R6_API int r6_sound_strings_row(const void *data, size_t size, int kind,
                                uint32_t index, r6_sound_strings_row_t *out);

#ifdef __cplusplus
}
#endif

#endif
