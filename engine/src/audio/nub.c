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
