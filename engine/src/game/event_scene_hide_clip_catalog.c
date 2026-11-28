/* Bounds-checked reader for packed event-scene hide-clip facts. */

#include "r6/r6_event_scene_hide_clip_catalog.h"

#include "core/internal.h"

enum {
    R6_EHC_HEADER_SIZE = 28,
    R6_EHC_SPAN_SIZE = 8,
    R6_EHC_NAMES = 4,
    R6_EHC_FUNCTIONS = 1,
    R6_EHC_TABLE_SIZE = 250,
    R6_EHC_ACCESSOR_SIZE = 553,
    R6_EHC_MAX_STRING = 96
};

static const unsigned char ehc_magic[8] = {
    'R', '6', 'E', 'H', 'C', 0, 1, 0
};

static const char ehc_prefix[] = "OSAKA_NGT_NML_";
static const char ehc_accessor[] = "EventSceneHideClip_GetHideModel";

static int ehc_header(const void *data, size_t size,
                      r6_event_scene_hide_clip_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_event_scene_hide_clip_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_EHC_HEADER_SIZE ||
            r6_memcmp(bytes, ehc_magic, sizeof(ehc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_EHC_NAMES ||
            !r6_u32(bytes, 16) || r6_u32(bytes, 20) != R6_EHC_TABLE_SIZE ||
            r6_u32(bytes, 24) != R6_EHC_ACCESSOR_SIZE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.name_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.table_size = r6_u32(bytes, 20);
    header.accessor_size = r6_u32(bytes, 24);
    base = R6_EHC_HEADER_SIZE +
           (size_t)(header.name_count + R6_EHC_FUNCTIONS) * R6_EHC_SPAN_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t ehc_strings_base(void) {
    return R6_EHC_HEADER_SIZE +
           (R6_EHC_NAMES + R6_EHC_FUNCTIONS) * R6_EHC_SPAN_SIZE;
}

static int ehc_span(const void *data,
                    const r6_event_scene_hide_clip_header_t *header,
                    uint32_t index, uint32_t *offset, uint32_t *length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t at = R6_EHC_HEADER_SIZE + (size_t)index * R6_EHC_SPAN_SIZE;
    size_t base = ehc_strings_base();
    size_t end = base + header->string_size;
    size_t want;
    if (index >= R6_EHC_NAMES + R6_EHC_FUNCTIONS) {
        return R6_ERR_ARG;
    }
    *offset = r6_u32(bytes, at);
    *length = r6_u32(bytes, at + 4);
    if (!*length || *length > R6_EHC_MAX_STRING ||
            (size_t)*offset < base || (size_t)*offset >= end ||
            (size_t)*length > end - (size_t)*offset - 1u ||
            bytes[(size_t)*offset + *length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (want = 0; want < *length; want++) {
        unsigned char value = bytes[(size_t)*offset + want];
        if (value < 0x20u || value > 0x7eu) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int ehc_copy(const void *data,
                    const r6_event_scene_hide_clip_header_t *header,
                    uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset = 0;
    uint32_t length = 0;
    int result = ehc_span(data, header, index, &offset, &length);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    (void)header;
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_event_scene_hide_clip_parse(
    const void *data, size_t size, r6_event_scene_hide_clip_header_t *out) {
    r6_event_scene_hide_clip_header_t header;
    char text[R6_EHC_MAX_STRING + 1];
    uint32_t index;
    int result = ehc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < header.name_count; index++) {
        result = ehc_copy(data, &header, index, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
        if (r6_memcmp(text, ehc_prefix,
                      sizeof(ehc_prefix) - 1u) != 0) {
            return R6_ERR_FORMAT;
        }
    }
    result = ehc_copy(data, &header, header.name_count, text, sizeof(text));
    if (result != R6_OK ||
            r6_memcmp(text, ehc_accessor,
                      sizeof(ehc_accessor)) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_event_scene_hide_clip_name(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity) {
    r6_event_scene_hide_clip_header_t header;
    int result = ehc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.name_count) {
        return R6_ERR_ARG;
    }
    return ehc_copy(data, &header, index, out, capacity);
}

int r6_event_scene_hide_clip_accessor(const void *data, size_t size,
                                      char *out, size_t capacity) {
    r6_event_scene_hide_clip_header_t header;
    int result = ehc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return ehc_copy(data, &header, header.name_count, out, capacity);
}
