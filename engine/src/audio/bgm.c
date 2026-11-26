/* Bounds-checked reader for packed BGM id/name/path rows. */

#include "core/internal.h"
#include "r6/r6_bgm.h"

static const unsigned char bgm_magic[8] = {
    'R', '6', 'B', 'G', 'M', 0, 1, 0
};

static int bgm_span(const unsigned char *bytes, size_t size, uint32_t offset,
                    const char **text, size_t *length) {
    size_t i;
    if (!bytes || !text || !length || offset >= size) {
        return R6_ERR_ARG;
    }
    for (i = offset; i < size && bytes[i]; i++) {
        /* scan inside the caller-owned blob */
    }
    if (i >= size) {
        return R6_ERR_FORMAT;
    }
    *text = (const char *)bytes + offset;
    *length = i - offset;
    return R6_OK;
}

int r6_bgm_parse(const void *data, size_t size, r6_bgm_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t count;
    uint32_t id_first;
    uint32_t strings_off;
    uint32_t strings_size;
    uint64_t required;
    if (!out || !bytes || size < R6_BGM_HEADER_SIZE ||
        r6_memcmp(bytes, bgm_magic, sizeof(bgm_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u || r6_u32(bytes, 28) != 0u) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(bytes, 12);
    id_first = r6_u32(bytes, 16);
    strings_off = r6_u32(bytes, 20);
    strings_size = r6_u32(bytes, 24);
    required = R6_BGM_HEADER_SIZE + (uint64_t)count * R6_BGM_RECORD_SIZE;
    if (count == 0 || (uint64_t)id_first + count > 0xffffu ||
        strings_off != required || strings_size == 0 ||
        (uint64_t)strings_off + strings_size != size || bytes[size - 1] != 0) {
        return R6_ERR_FORMAT;
    }
    out->version = 1;
    out->count = count;
    out->id_first = id_first;
    out->strings_off = strings_off;
    out->strings_size = strings_size;
    return R6_OK;
}

const char *r6_bgm_string(const void *data, size_t size, uint32_t offset) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_bgm_header header;
    const char *text = NULL;
    size_t length = 0;
    if (r6_bgm_parse(data, size, &header) != R6_OK ||
        offset < header.strings_off || offset >= size ||
        bgm_span(bytes, size, offset, &text, &length) != R6_OK) {
        return NULL;
    }
    return text;
}

static int bgm_record(const unsigned char *bytes, const r6_bgm_header *header,
                      uint32_t index, r6_bgm_record *out) {
    const unsigned char *at;
    const char *text;
    size_t length;
    if (!out || index >= header->count) {
        return R6_ERR_ARG;
    }
    at = bytes + R6_BGM_HEADER_SIZE + (size_t)index * R6_BGM_RECORD_SIZE;
    r6_memcpy(out, at, R6_BGM_RECORD_SIZE);
    if (out->id < header->id_first ||
        (uint32_t)out->id >= header->id_first + header->count ||
        out->name_off < header->strings_off ||
        out->path_off < header->strings_off ||
        bgm_span(bytes, header->strings_off + header->strings_size,
                 out->name_off, &text, &length) != R6_OK ||
        bgm_span(bytes, header->strings_off + header->strings_size,
                 out->path_off, &text, &length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_bgm_find_id(const void *data, size_t size, uint16_t id,
                   r6_bgm_record *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_bgm_header header;
    r6_bgm_record record;
    uint32_t index;
    int rc;
    if (!out || r6_bgm_parse(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    if (id < header.id_first ||
        (uint32_t)id >= header.id_first + header.count) {
        return R6_ERR_NOT_FOUND;
    }
    index = (uint32_t)id - header.id_first;
    rc = bgm_record(bytes, &header, index, &record);
    if (rc != R6_OK || record.id != id) {
        return rc == R6_OK ? R6_ERR_FORMAT : rc;
    }
    *out = record;
    return R6_OK;
}

int r6_bgm_find_name(const void *data, size_t size, const char *name,
                     r6_bgm_record *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_bgm_header header;
    r6_bgm_record record;
    const char *text;
    size_t length;
    size_t needle = 0;
    uint32_t index;
    int rc;
    if (!out || !name || r6_bgm_parse(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    while (name[needle]) {
        needle++;
    }
    if (needle == 0) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < header.count; index++) {
        rc = bgm_record(bytes, &header, index, &record);
        if (rc != R6_OK) {
            return rc;
        }
        rc = bgm_span(bytes, header.strings_off + header.strings_size,
                      record.name_off, &text, &length);
        if (rc != R6_OK) {
            return rc;
        }
        if (length >= needle) {
            size_t i;
            for (i = 0; i + needle <= length; i++) {
                if (r6_memcmp(text + i, name, needle) == 0) {
                    *out = record;
                    return R6_OK;
                }
            }
        }
    }
    return R6_ERR_NOT_FOUND;
}

static float bgm_f32(const unsigned char *bytes, size_t offset) {
    float value;
    r6_memcpy(&value, bytes + offset, sizeof(value));
    return value;
}

static void bgm_put_f32(unsigned char *bytes, size_t offset, float value) {
    r6_memcpy(bytes + offset, &value, sizeof(value));
}

static void bgm_put_u32(unsigned char *bytes, size_t offset, uint32_t value) {
    bytes[offset] = (unsigned char)value;
    bytes[offset + 1] = (unsigned char)(value >> 8);
    bytes[offset + 2] = (unsigned char)(value >> 16);
    bytes[offset + 3] = (unsigned char)(value >> 24);
}

int r6_bgm_fade_read(const void *data, size_t size, r6_bgm_fade_state *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    if (!bytes || !out || size < R6_BGM_FADE_RECORD_SIZE) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    out->state = r6_u32(bytes, R6_BGM_FADE_STATE_OFFSET);
    out->flag = bytes[R6_BGM_FADE_FLAG_OFFSET];
    out->mode = r6_u32(bytes, R6_BGM_FADE_MODE_OFFSET);
    out->frames = r6_u32(bytes, R6_BGM_FADE_FRAMES_OFFSET);
    out->step = bgm_f32(bytes, R6_BGM_FADE_STEP_OFFSET);
    out->volume = bgm_f32(bytes, R6_BGM_FADE_VOLUME_OFFSET);
    out->voice = r6_u32(bytes, R6_BGM_FADE_VOICE_OFFSET);
    out->channel = r6_u32(bytes, R6_BGM_FADE_CHANNEL_OFFSET);
    out->fader = bgm_f32(bytes, R6_BGM_FADER_OFFSET);
    return R6_OK;
}

uint32_t r6_bgm_fade_begin(void *data, size_t size, int32_t ms,
                           uint32_t *stop_voice) {
    unsigned char *bytes = (unsigned char *)data;
    r6_bgm_fade_state state;
    double ticks;
    if (!bytes || !stop_voice || size < R6_BGM_FADE_RECORD_SIZE) {
        return R6_BGM_FADE_BAD_ARG;
    }
    *stop_voice = 0;
    if (r6_bgm_fade_read(bytes, size, &state) != R6_OK) {
        return R6_BGM_FADE_BAD_ARG;
    }
    if (state.mode == R6_BGM_STATE_FADING) {
        return R6_BGM_FADE_ALREADY_FADING;
    }
    if (!state.state) {
        return R6_BGM_FADE_NOT_PLAYING;
    }
    ticks = (double)ms / 5.333;
    if (state.state == R6_BGM_STATE_PLAYING && ticks > 0.0 && !state.flag) {
        uint32_t frames = (uint32_t)ticks;
        bgm_put_u32(bytes, R6_BGM_FADE_MODE_OFFSET, R6_BGM_STATE_FADING);
        bgm_put_u32(bytes, R6_BGM_FADE_FRAMES_OFFSET, frames);
        bgm_put_f32(bytes, R6_BGM_FADE_STEP_OFFSET,
                    -state.volume / (float)frames);
        return 0;
    }
    bgm_put_u32(bytes, R6_BGM_FADE_STATE_OFFSET, R6_BGM_STATE_STOPPED);
    bgm_put_f32(bytes, R6_BGM_FADER_OFFSET, 0.0f);
    *stop_voice = state.voice;
    return 0;
}

int r6_bgm_manager_read(const void *data, size_t size,
                        r6_bgm_manager_state *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    if (!bytes || !out || size < R6_BGM_MANAGER_SIZE) {
        return R6_ERR_ARG;
    }
    out->current = (int32_t)r6_u32(bytes, R6_BGM_MANAGER_CURRENT_OFFSET);
    out->next = (int32_t)r6_u32(bytes, R6_BGM_MANAGER_NEXT_OFFSET);
    return R6_OK;
}

int r6_bgm_manager_select(void *data, size_t size, int32_t id,
                          int32_t *action) {
    unsigned char *bytes = (unsigned char *)data;
    r6_bgm_manager_state state;
    if (!bytes || !action || size < R6_BGM_MANAGER_SIZE) {
        return R6_ERR_ARG;
    }
    if (r6_bgm_manager_read(bytes, size, &state) != R6_OK) {
        return R6_ERR_ARG;
    }
    if (id == R6_BGM_NO_CHANGE) {
        *action = R6_BGM_ACTION_NONE;
        return R6_OK;
    }
    if (id == R6_BGM_NO_SOUND_ID) {
        state.current = R6_BGM_NO_CHANGE;
        *action = R6_BGM_ACTION_FADE;
    } else if (id == R6_BGM_RANDOM_ID) {
        *action = R6_BGM_ACTION_REJECTED;
    } else if (state.current == R6_BGM_NO_CHANGE) {
        state.current = id;
        *action = R6_BGM_ACTION_PLAY;
    } else if (state.current == id) {
        *action = R6_BGM_ACTION_ALREADY;
    } else {
        state.next = id;
        *action = R6_BGM_ACTION_QUEUE;
    }
    bgm_put_u32(bytes, R6_BGM_MANAGER_CURRENT_OFFSET,
                (uint32_t)state.current);
    bgm_put_u32(bytes, R6_BGM_MANAGER_NEXT_OFFSET, (uint32_t)state.next);
    return R6_OK;
}
