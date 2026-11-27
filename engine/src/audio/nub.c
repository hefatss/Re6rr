#include "core/internal.h"
#include "r6/r6_audio.h"

#define NUB_HEADER_SIZE 0x20u
#define NUB_TONE_SIZE 0xd0u
#define NUB_VERSION 0x00010201u

static float nub_f32(const void *data, size_t offset) {
    float value;
    r6_memcpy(&value, (const unsigned char *)data + offset, sizeof(value));
    return value;
}

static uint64_t nub_u64(const void *data, size_t offset) {
    return (uint64_t)r6_u32(data, offset) |
           ((uint64_t)r6_u32(data, offset + 4u) << 32);
}

static int nub_header(const void *data, size_t size, r6_nub_header *header) {
    if (!data || !header || size < NUB_HEADER_SIZE || r6_u32(data, 0) !=
        NUB_VERSION) {
        return R6_ERR_FORMAT;
    }
    if (r6_u32(data, 4) != 0 || r6_u32(data, 0x18) != 0x20) {
        return R6_ERR_FORMAT;
    }
    header->version = NUB_VERSION;
    header->bank_id = r6_u32(data, 8);
    header->tone_count = r6_u32(data, 0x0c);
    header->header_size = r6_u32(data, 0x10);
    header->data_size = r6_u32(data, 0x14);
    header->first_record = r6_u32(data, 0x1c);
    if (header->header_size < NUB_HEADER_SIZE ||
        (size_t)header->header_size > size ||
        (uint64_t)header->header_size + header->data_size > size ||
        header->first_record < NUB_HEADER_SIZE ||
        header->first_record > header->header_size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static uint32_t nub_slot_offset(const void *data, size_t size, uint32_t index) {
    size_t at = NUB_HEADER_SIZE + (size_t)index * 4u;
    return at + 4u <= size ? r6_u32(data, at) : 0u;
}

static uint32_t nub_slot_count(const r6_nub_header *header) {
    return (header->first_record - NUB_HEADER_SIZE) / 4u;
}

static uint32_t nub_tone_offset(const void *data, size_t size,
                                const r6_nub_header *header, uint32_t index) {
    uint32_t slots = nub_slot_count(header);
    uint32_t i, seen = 0;
    for (i = 0; i < slots; i++) {
        uint32_t value = nub_slot_offset(data, size, i);
        if (value) {
            if (seen == index) {
                return value;
            }
            seen++;
        }
    }
    return 0;
}

static int nub_tone(const void *data, const r6_nub_header *header,
                    uint32_t index, uint32_t offset, r6_nub_tone *out) {
    const unsigned char *record;
    uint16_t bits, block_align, format_tag, format_channels;
    uint32_t length, data_offset, rate, byte_rate, width, loop_flag;
    if (offset < header->first_record ||
        (uint64_t)offset + NUB_TONE_SIZE > header->header_size) {
        return R6_ERR_FORMAT;
    }
    record = (const unsigned char *)data + offset;
    if (r6_memcmp(record, "wav\0", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    bits = r6_u16(data, offset + 0xca);
    block_align = r6_u16(data, offset + 0xc8);
    width = bits / 8u;
    if (width == 0 || block_align == 0) {
        return R6_ERR_FORMAT;
    }
    format_tag = r6_u16(data, offset + 0xbc);
    format_channels = r6_u16(data, offset + 0xbe);
    rate = r6_u32(data, offset + 0xc0);
    byte_rate = r6_u32(data, offset + 0xc4);
    length = r6_u32(data, offset + 0x14);
    data_offset = r6_u32(data, offset + 0x18);
    if (format_tag != 1 || format_channels != block_align / width ||
        length % block_align != 0 ||
        (uint64_t)data_offset + length > header->data_size ||
        byte_rate != rate * block_align) {
        return R6_ERR_FORMAT;
    }
    loop_flag = r6_u32(data, offset + 0x28);
    out->index = index;
    out->slot = r6_u32(data, offset + 8);
    out->group = r6_u32(data, offset + 0x0c);
    out->record_offset = offset;
    out->length = length;
    out->data_offset = data_offset;
    out->flags = r6_u32(data, offset + 0x10);
    out->format_count = r6_u32(data, offset + 0x1c);
    out->rate = rate;
    out->channels = block_align / width;
    out->bits = bits;
    out->loop_flag = loop_flag;
    out->volume = nub_f32(data, offset + 0x34);
    out->three_d_param_no = r6_u32(data, offset + 0x54);
    out->format_tag = format_tag;
    out->format_channels = format_channels;
    out->block_align = block_align;
    out->byte_rate = byte_rate;
    return R6_OK;
}

int r6_nub_parse(const void *data, size_t size, r6_nub_header *header,
                 r6_nub_tone *tones, size_t capacity) {
    r6_nub_header parsed;
    uint32_t count = 0;
    uint32_t slots;
    uint32_t index;
    int rc = nub_header(data, size, &parsed);
    if (rc != R6_OK) {
        return rc;
    }
    slots = nub_slot_count(&parsed);
    for (index = 0; index < slots; index++) {
        if (nub_slot_offset(data, size, index) != 0) {
            count++;
        }
    }
    if (count != parsed.tone_count) {
        return R6_ERR_FORMAT;
    }
    if (header) {
        *header = parsed;
    }
    if (capacity < count || !tones) {
        return R6_ERR_BUFFER;
    }
    for (index = 0; index < count; index++) {
        rc = nub_tone(data, &parsed, index,
                      nub_tone_offset(data, size, &parsed, index),
                      &tones[index]);
        if (rc != R6_OK) {
            return rc;
        }
    }
    return R6_OK;
}

int r6_nub_tone_control(const void *data, size_t size,
                        const r6_nub_tone *tone, r6_nub_control *out) {
    if (!data || !tone || !out ||
        (uint64_t)tone->record_offset + NUB_TONE_SIZE > size) {
        return R6_ERR_ARG;
    }
    out->three_d_float_a = nub_f32(data, tone->record_offset + 0x44);
    out->three_d_float_b = nub_f32(data, tone->record_offset + 0x50);
    out->three_d_param_no = r6_u32(data, tone->record_offset + 0x54);
    out->volume_cap = nub_f32(data, tone->record_offset + 0x58);
    out->pan_cap = nub_f32(data, tone->record_offset + 0x5c);
    out->bus_id = r6_u32(data, tone->record_offset + 0x60);
    out->voice_bus = r6_u32(data, tone->record_offset + 0x68);
    return R6_OK;
}

int r6_nub_tone_getters(const void *data, size_t size,
                        const r6_nub_tone *tone, r6_nub_getters *out) {
    uint32_t codec;
    uint32_t length;
    uint32_t block_align;
    if (!data || !tone || !out ||
        (uint64_t)tone->record_offset + NUB_TONE_SIZE > size) {
        return R6_ERR_ARG;
    }
    codec = r6_u32(data, tone->record_offset + 0x0c);
    if (codec != 1u) {
        return R6_ERR_FORMAT;
    }
    length = r6_u32(data, tone->record_offset + 0x14);
    block_align = r6_u16(data, tone->record_offset + 0xc8);
    if (!block_align || length % block_align != 0u ||
        length != tone->length || block_align != tone->block_align) {
        return R6_ERR_FORMAT;
    }
    out->user_param[0] = r6_u32(data, tone->record_offset + 0xac);
    out->user_param[1] = r6_u32(data, tone->record_offset + 0xb0);
    out->user_param[2] = r6_u32(data, tone->record_offset + 0xb4);
    out->user_param[3] = r6_u32(data, tone->record_offset + 0xb8);
    out->total_samples = length / block_align;
    out->codec = codec;
    return R6_OK;
}

int r6_nub_setup_bytes(const void *data, size_t size,
                       const r6_nub_tone *tone,
                       unsigned char out[R6_NUB_SETUP_BYTES]) {
    if (!data || !tone || !out ||
        (uint64_t)tone->record_offset + NUB_TONE_SIZE > size) {
        return R6_ERR_ARG;
    }
    r6_memcpy(out, (const unsigned char *)data + tone->record_offset +
              R6_NUB_SETUP_OFFSET, R6_NUB_SETUP_BYTES);
    return R6_OK;
}

int r6_nub_pcm(const void *data, size_t size, const r6_nub_header *header,
               const r6_nub_tone *tone, const void **out, size_t *out_size) {
    uint64_t start;
    if (!data || !header || !tone || !out || !out_size) {
        return R6_ERR_ARG;
    }
    start = (uint64_t)header->header_size + tone->data_offset;
    if (start > size || (uint64_t)tone->length > size - start) {
        return R6_ERR_BUFFER;
    }
    *out = (const unsigned char *)data + start;
    *out_size = tone->length;
    return R6_OK;
}

int r6_bank_setup_init(r6_bank_setup_view *view, const void *data,
                       size_t size, r6_bank_setup_tone *tones,
                       size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t count;
    uint32_t table;
    uint32_t index;
    if (!view) {
        return R6_ERR_ARG;
    }
    r6_memset(view, 0, sizeof(*view));
    if (!bytes || size < NUB_HEADER_SIZE) {
        return R6_ERR_BUFFER;
    }
    if (r6_u32(data, 0) != NUB_VERSION) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(data, 0x0c);
    table = r6_u32(data, 0x18);
    r6_memcpy(view->version, bytes, sizeof(view->version));
    view->tone_count = count;
    view->data_offset = r6_u32(data, 0x10);
    view->data_size = r6_u32(data, 0x14);
    view->record_table = table;
    if ((uint64_t)table > size ||
        (uint64_t)count * 4u > (uint64_t)size - table) {
        return R6_ERR_FORMAT;
    }
    if (count && (!tones || capacity < count)) {
        return R6_ERR_BUFFER;
    }
    for (index = 0; index < count; index++) {
        uint32_t record = r6_u32(data, (size_t)table + (size_t)index * 4u);
        if ((uint64_t)record + 0xC4u > size) {
            return R6_ERR_FORMAT;
        }
        tones[index].length = r6_u32(data, (size_t)record + 0x14u);
        tones[index].data_offset = r6_u32(data, (size_t)record + 0x18u);
        tones[index].formats = r6_u32(data, (size_t)record + 0x1Cu);
    }
    view->tones = count ? tones : NULL;
    return R6_OK;
}

int32_t r6_audio_fade_frames_to_ms(int32_t now_frame, int32_t max_frame) {
    int64_t frames = (int64_t)max_frame - (int64_t)now_frame;
    return (int32_t)((frames / R6_AUDIO_FADE_FRAME_RATE) * 1000);
}

int64_t r6_audio_stream_reserve(int64_t total, int64_t size) {
    if (size < 0 || total + size > R6_AUDIO_STREAM_LIMIT) {
        return -1;
    }
    return total + size;
}

int r6_sound_init_parse(const void *data, size_t size, r6_sound_init *out) {
    if (!out) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    if (!data || size < R6_SOUND_CONFIG_SIZE) {
        return R6_ERR_ARG;
    }
    out->bank_num = r6_u32(data, 0);
    out->reqid_num = r6_u32(data, 4);
    out->stream_num = r6_u32(data, 8);
    if (out->bank_num > R6_SOUND_BANK_MAX ||
        out->reqid_num > R6_SOUND_REQUEST_MAX ||
        out->stream_num < R6_SOUND_STREAM_MIN ||
        out->stream_num > R6_SOUND_STREAM_MAX) {
        r6_memset(out, 0, sizeof(*out));
        return R6_ERR_FORMAT;
    }
    out->pointers[0] = nub_u64(data, R6_SOUND_CONFIG_BIN_OFFSET);
    out->pointers[1] = nub_u64(data, R6_SOUND_CONFIG_3D_OFFSET);
    out->pointers[2] = nub_u64(data, R6_SOUND_CORE_INIT_OFFSET);
    out->bank_bytes = out->bank_num * R6_SOUND_BANK_STRIDE;
    out->request_bytes = out->reqid_num * R6_SOUND_REQUEST_STRIDE;
    out->stream_bytes = out->stream_num * R6_SOUND_STREAM_STRIDE;
    return R6_OK;
}

int r6_sound_impl_tail(r6_sound_impl_tail_t *out) {
    if (!out) {
        return R6_ERR_ARG;
    }
    out->size = R6_SOUND_IMPL_SIZE;
    out->zero_quad_offset = 0x60u;
    out->zero_quad_count = 4u;
    out->volume_a_offset = 0x80u;
    out->volume_b_offset = 0x88u;
    out->sentinel_offset = 0x90u;
    out->sentinel_value = 0xFFFFFFFFu;
    out->volume_value = 1.0f;
    return R6_OK;
}

int r6_sound_bank_slot(const void *data, size_t size, uint32_t index,
                       r6_sound_bank_slot_t *out) {
    size_t at = (size_t)index * R6_SOUND_BANK_STRIDE;
    if (!data || !out ||
        at + R6_SOUND_BANK_STRIDE > size) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    out->handle = r6_u32(data, at + R6_SOUND_BANK_HANDLE_OFFSET);
    out->state = r6_u32(data, at + R6_SOUND_BANK_STATE_OFFSET);
    out->ready = out->state == R6_SOUND_BANK_STATE_READY;
    return R6_OK;
}

int r6_sound_loop_record(const void *data, size_t size, uint32_t index,
                         r6_sound_loop_record_t *out) {
    size_t at = (size_t)index * R6_SOUND_LOOP_STRIDE;
    if (!data || !out || at + R6_SOUND_LOOP_STRIDE > size) {
        return R6_ERR_ARG;
    }
    out->flag = r6_u32(data, at);
    out->tone = r6_u32(data, at + 4u);
    return R6_OK;
}

int r6_sound_positional_record(const void *data, size_t size, uint32_t index,
                               r6_sound_positional_record_t *out) {
    size_t at = (size_t)index * R6_SOUND_POSITIONAL_STRIDE;
    if (!data || !out || at + R6_SOUND_POSITIONAL_STRIDE > size) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    out->bank = r6_u32(data, at);
    out->tone = (int32_t)r6_u32(data, at + 4u);
    out->frames = (int32_t)r6_u32(data, at + 8u);
    out->x = nub_f32(data, at + 0x0cu);
    out->y = nub_f32(data, at + 0x10u);
    out->z = nub_f32(data, at + 0x14u);
    return R6_OK;
}

int r6_sound_bin_parse(const void *data, size_t size, r6_sound_bin *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t i;
    if (!out) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    if (!bytes || size < R6_SOUND_BIN_HEADER_SIZE ||
        r6_u32(bytes, 0) != 0x6373756Eu || /* "nusc" */
        r6_u32(bytes, 4) != 0x00030201u) {
        return R6_ERR_FORMAT;
    }
    out->size = r6_u32(bytes, 8);
    out->header_size = r6_u32(bytes, 0x0cu);
    out->float_offset = r6_u32(bytes, R6_SOUND_BIN_FLOAT_OFFSET);
    if (out->size != size || out->header_size != R6_SOUND_BIN_HEADER_SIZE ||
        out->float_offset > size) {
        r6_memset(out, 0, sizeof(*out));
        return R6_ERR_FORMAT;
    }
    for (i = 0; i < R6_SOUND_BIN_SECTIONS; i++) {
        size_t at = R6_SOUND_BIN_PAIRS_OFFSET + (size_t)i * 8u;
        out->counts[i] = r6_u32(bytes, at);
        out->offsets[i] = r6_u32(bytes, at + 4u);
        if (out->offsets[i] > size) {
            r6_memset(out, 0, sizeof(*out));
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

int r6_bank_slot_find(const void *slots, size_t size, uint32_t *out) {
    const unsigned char *bytes = (const unsigned char *)slots;
    uint32_t index;
    if (!bytes || !out || size < R6_BANK_SLOT_TABLE_SIZE) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < R6_BANK_SLOT_COUNT; index++) {
        size_t at = (size_t)index * R6_BANK_SLOT_STRIDE +
                    R6_BANK_SLOT_POINTER_OFFSET;
        if (!r6_u32(bytes, at) && !r6_u32(bytes, at + 4u)) {
            *out = index;
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

static size_t strings_copy(const unsigned char *source, size_t available,
                           char *target, size_t capacity) {
    size_t length = 0;
    if (!capacity) {
        return 0;
    }
    while (length < available && source[length]) {
        length++;
    }
    if (length >= capacity) {
        length = capacity - 1u;
    }
    r6_memset(target, 0, capacity);
    r6_memcpy(target, source, length);
    return length;
}

int r6_sound_strings_parse(const void *data, size_t size, int kind,
                           r6_sound_strings_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sound_strings_header header;
    uint64_t expected;
    if (!bytes || !out || size < R6_SOUND_STRINGS_HEADER_SIZE ||
        (kind != R6_SOUND_STRINGS_BANK && kind != R6_SOUND_STRINGS_TONE) ||
        r6_u32(bytes, 0) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(&header, 0, sizeof(header));
    header.version = 1u;
    if (kind == R6_SOUND_STRINGS_BANK) {
        header.count = r6_u32(bytes, 4);
        header.size = r6_u32(bytes, 8);
        header.name_size = r6_u32(bytes, 0x0c);
        if (!header.count || !header.name_size ||
            header.name_size > R6_SOUND_STRINGS_BANK_ROW_SIZE) {
            return R6_ERR_FORMAT;
        }
        expected = R6_SOUND_STRINGS_HEADER_SIZE +
                   (uint64_t)header.count * R6_SOUND_STRINGS_BANK_ROW_SIZE -
                   (R6_SOUND_STRINGS_BANK_ROW_SIZE - header.name_size);
        header.rows_off = R6_SOUND_STRINGS_HEADER_SIZE;
        header.row_size = R6_SOUND_STRINGS_BANK_ROW_SIZE;
    } else {
        header.bank_id = r6_u32(bytes, 4);
        header.count = r6_u32(bytes, 8);
        header.size = r6_u32(bytes, 0x0c);
        header.name_size = r6_u32(bytes, 0x10);
        header.path_size = r6_u32(bytes, 0x14);
        if (header.name_size != R6_SOUND_STRINGS_FIELD_SIZE ||
            header.path_size != R6_SOUND_STRINGS_FIELD_SIZE) {
            return R6_ERR_FORMAT;
        }
        expected = R6_SOUND_STRINGS_TONE_ROWS_OFFSET +
                   (uint64_t)header.count * R6_SOUND_STRINGS_TONE_ROW_SIZE;
        header.rows_off = R6_SOUND_STRINGS_TONE_ROWS_OFFSET;
        header.row_size = R6_SOUND_STRINGS_TONE_ROW_SIZE;
    }
    if (header.size != size || header.size != expected) {
        return R6_ERR_FORMAT;
    }
    *out = header;
    return R6_OK;
}

int r6_sound_strings_row(const void *data, size_t size, int kind,
                         uint32_t index, r6_sound_strings_row_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sound_strings_header header;
    size_t at;
    size_t available;
    int result = r6_sound_strings_parse(data, size, kind, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out || index >= header.count) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    at = header.rows_off + (size_t)index * header.row_size;
    if (at >= size) {
        return R6_ERR_FORMAT;
    }
    available = size - at;
    if (available > header.row_size) {
        available = header.row_size;
    }
    if (kind == R6_SOUND_STRINGS_BANK) {
        size_t name_size = header.name_size;
        if (name_size > available) {
            name_size = available;
        }
        strings_copy(bytes + at, name_size, out->name, sizeof(out->name));
        if (header.name_size + 4u <= available) {
            out->id = r6_u32(bytes, at + header.name_size);
        }
    } else {
        strings_copy(bytes + at, available, out->name, sizeof(out->name));
        if (available > header.name_size) {
            strings_copy(bytes + at + header.name_size,
                         available - header.name_size,
                         out->value, sizeof(out->value));
        }
    }
    return R6_OK;
}

int r6_sound_strings_find(const void *data, size_t size, int kind,
                          const char *name, uint32_t *index) {
    r6_sound_strings_header header;
    size_t wanted;
    uint32_t at;
    int result = r6_sound_strings_parse(data, size, kind, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!name) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.count; at++) {
        r6_sound_strings_row_t row;
        result = r6_sound_strings_row(data, size, kind, at, &row);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(row.name) == wanted &&
            r6_memcmp(row.name, name, wanted) == 0) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_sound_strings_find_value(const void *data, size_t size,
                                const char *value, uint32_t *index) {
    r6_sound_strings_header header;
    size_t wanted;
    uint32_t at;
    int result = r6_sound_strings_parse(data, size, R6_SOUND_STRINGS_TONE,
                                        &header);
    if (result != R6_OK) {
        return result;
    }
    if (!value) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(value);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.count; at++) {
        r6_sound_strings_row_t row;
        result = r6_sound_strings_row(data, size, R6_SOUND_STRINGS_TONE, at,
                                      &row);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(row.value) == wanted &&
            r6_memcmp(row.value, value, wanted) == 0) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

#define R6_AUDIO_BINDING_NONE (-1)

static const r6_audio_binding_t audio_bindings[] = {
    {"PlaySE", 0x1407815D0ull, "playSe", 2, R6_AUDIO_BINDING_NONE},
    {"PlaySEOfBank", 0x140781650ull, "playSe", R6_AUDIO_BINDING_NONE,
     R6_AUDIO_BINDING_NONE},
    {"PlaySELoop", 0x140781740ull, "playSeLoop", 2, R6_AUDIO_BINDING_NONE},
    {"PlaySELoopOfBank", 0x140781830ull, "playSeLoop", R6_AUDIO_BINDING_NONE,
     R6_AUDIO_BINDING_NONE},
    {"StopSELoop", 0x140781990ull, "stopSeLoop", R6_AUDIO_BINDING_NONE,
     R6_AUDIO_BINDING_NONE},
    {"PlaySEDecide", 0x140781A10ull, "playSe", 2, 0x2F},
    {"PlaySECancel", 0x140781A40ull, "playSe", 2, 0x07},
    {"PlaySEMove", 0x140781A70ull, "playSe", 2, 0x0F},
    {"PlayBGM", 0x140781AA0ull, "playBgm", R6_AUDIO_BINDING_NONE,
     R6_AUDIO_BINDING_NONE},
    {"PlayBGMByName", 0x140781B20ull, "playBgmByName",
     R6_AUDIO_BINDING_NONE, R6_AUDIO_BINDING_NONE},
    {"FadeOutBGM", 0x140781BA0ull, "fadeOutBgm", R6_AUDIO_BINDING_NONE,
     R6_AUDIO_BINDING_NONE},
    {"StopBGM", 0x140781CA0ull, "stopBgm", R6_AUDIO_BINDING_NONE,
     R6_AUDIO_BINDING_NONE}
};

uint32_t r6_audio_binding_count(void) {
    return (uint32_t)(sizeof(audio_bindings) / sizeof(audio_bindings[0]));
}

int r6_audio_binding(uint32_t index, r6_audio_binding_t *out) {
    if (!out || index >= r6_audio_binding_count()) {
        return R6_ERR_ARG;
    }
    r6_memcpy(out, &audio_bindings[index], sizeof(*out));
    return R6_OK;
}

int r6_audio_binding_find(const char *name, r6_audio_binding_t *out) {
    uint32_t index;
    if (!name) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < r6_audio_binding_count(); index++) {
        if (r6_strlen(audio_bindings[index].name) == r6_strlen(name) &&
            r6_memcmp(audio_bindings[index].name, name,
                      r6_strlen(name)) == 0) {
            if (out) {
                r6_memcpy(out, &audio_bindings[index], sizeof(*out));
            }
            return (int)index;
        }
    }
    return R6_ERR_NOT_FOUND;
}

void r6_audio_layout_facts(r6_audio_layout_facts_t *out) {
    if (!out) {
        return;
    }
    r6_memset(out, 0, sizeof(*out));
    out->bank_slots = 0x40u;
    out->slot_stride = 0x804u;
    out->slot_bank_ptr = 0x42u;
    out->slot_data_ptr = 0x44u;
    out->slot_voice_ids = 0x46u;
    out->record_base = 0x108u;
    out->record_stride = 0x2010u;
    out->record_voice_ids = 0x10u;
    out->stream_reserve = 0x80508u;
    out->stream_limit = 0x20000000u;
    out->version[0] = 1u;
    out->version[1] = 2u;
    out->version[2] = 1u;
    out->voice_slots = 0x40u;
    out->voice_record_stride = 0xA0u;
    out->voice_meta_base = 0x2800u;
    out->voice_meta_stride = 0xCu;
}
