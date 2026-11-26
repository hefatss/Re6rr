/* Reader for the packed shipped BGM id/name/path table.
 *
 * Rows are recovered from wmn6r.exe by tools/engine/audio_events.py and packed
 * by tools/engine/bgm_catalog.py. The core validates offsets and returns copies
 * of fixed records; names and paths stay in the caller-owned blob. No files,
 * allocation, CRT or libm.
 */
#ifndef R6_BGM_H
#define R6_BGM_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_BGM_HEADER_SIZE 32u
#define R6_BGM_RECORD_SIZE 12u

enum {
    R6_BGM_FLAG_STOP = 0x0001,
    R6_BGM_FLAG_RANDOM = 0x0002
};

typedef struct r6_bgm_header {
    uint32_t version;
    uint32_t count;
    uint32_t id_first;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_bgm_header;

typedef struct r6_bgm_record {
    uint16_t id;
    uint16_t flags;
    uint32_t name_off;
    uint32_t path_off;
} r6_bgm_record;

R6_API int r6_bgm_parse(const void *data, size_t size, r6_bgm_header *out);

/* Direct lookup by shipped id; ids are contiguous from id_first. */
R6_API int r6_bgm_find_id(const void *data, size_t size, uint16_t id,
                          r6_bgm_record *out);

/* Substring lookup by name, matching audio_events.bgm_by_name(). */
R6_API int r6_bgm_find_name(const void *data, size_t size, const char *name,
                            r6_bgm_record *out);

/* NUL-terminated interned name or path, or NULL outside the string table. */
R6_API const char *r6_bgm_string(const void *data, size_t size,
                                 uint32_t offset);

/* nuSound2StreamFadeOut (FUN_180016850) reads and updates a host-owned stream
 * record. Field offsets and state codes come from AUDIO_NUB.md. */
enum {
    R6_BGM_FADE_STATE_OFFSET = 0x28C,
    R6_BGM_FADE_FLAG_OFFSET = 0x293,
    R6_BGM_FADE_MODE_OFFSET = 0x294,
    R6_BGM_FADE_FRAMES_OFFSET = 0x298,
    R6_BGM_FADE_STEP_OFFSET = 0x29C,
    R6_BGM_FADE_VOLUME_OFFSET = 0x2A0,
    R6_BGM_FADE_VOICE_OFFSET = 0x2A8,
    R6_BGM_FADE_CHANNEL_OFFSET = 0x148,
    R6_BGM_FADER_OFFSET = 0x2C0,
    R6_BGM_FADE_RECORD_SIZE = 0x2C4,
    R6_BGM_STATE_FADING = 2,
    R6_BGM_STATE_PLAYING = 3,
    R6_BGM_STATE_STOPPED = 5,
    R6_BGM_FADE_INVALID_HANDLE = 0x8000000Au,
    R6_BGM_FADE_NOT_PLAYING = 0x8000000Bu,
    R6_BGM_FADE_ALREADY_FADING = 0x80000000u,
    R6_BGM_FADE_BAD_ARG = 0xFFFFFFFFu
};

typedef struct r6_bgm_fade_state {
    uint32_t state;
    uint8_t flag;
    uint32_t mode;
    uint32_t frames;
    float step;
    float volume;
    uint32_t voice;
    uint32_t channel;
    float fader;
} r6_bgm_fade_state;

R6_API int r6_bgm_fade_read(const void *data, size_t size,
                            r6_bgm_fade_state *out);

/* Start a fade or take the native fallback-stop path. On success the stream
 * bytes are updated in place and *stop_voice receives the voice id to stop
 * (zero for the fade path). Returns a native status code, or
 * R6_BGM_FADE_BAD_ARG when arguments or record size are invalid. */
R6_API uint32_t r6_bgm_fade_begin(void *data, size_t size, int32_t ms,
                                  uint32_t *stop_voice);

/* SoundManager::playBGM state at +0x44c/+0x450 (FUN_1407d6940). */
enum {
    R6_BGM_MANAGER_CURRENT_OFFSET = 0x44C,
    R6_BGM_MANAGER_NEXT_OFFSET = 0x450,
    R6_BGM_MANAGER_SIZE = 0x454,
    R6_BGM_NO_CHANGE = -1,
    R6_BGM_NO_SOUND_ID = 0x8C,
    R6_BGM_RANDOM_ID = 0x8D,
    R6_BGM_STREAM_HANDLE = 0
};

enum {
    R6_BGM_ACTION_NONE = 0,
    R6_BGM_ACTION_PLAY = 1,
    R6_BGM_ACTION_FADE = 2,
    R6_BGM_ACTION_QUEUE = 3,
    R6_BGM_ACTION_ALREADY = 4,
    R6_BGM_ACTION_REJECTED = 5
};

typedef struct r6_bgm_manager_state {
    int32_t current;
    int32_t next;
} r6_bgm_manager_state;

R6_API int r6_bgm_manager_read(const void *data, size_t size,
                               r6_bgm_manager_state *out);

/* Apply the shipped id dispatch. The returned action tells the host whether
 * to start a stream, fade the current one, queue a change or do nothing. */
R6_API int r6_bgm_manager_select(void *data, size_t size, int32_t id,
                                 int32_t *action);

#ifdef __cplusplus
}
#endif

#endif
