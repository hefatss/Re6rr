#include "r6/r6_glsl_manifest.h"

#include "core/internal.h"

/* All multi-byte fields are little-endian, matching the Python emitter. */
static uint16_t r6_glsl_get16(const unsigned char *at) {
    return (uint16_t)(at[0] | ((uint16_t)at[1] << 8));
}

static uint32_t r6_glsl_get32(const unsigned char *at) {
    return (uint32_t)at[0] | ((uint32_t)at[1] << 8) |
           ((uint32_t)at[2] << 16) | ((uint32_t)at[3] << 24);
}

static int r6_glsl_table_ok(uint32_t first, uint64_t bytes,
                            uint32_t low, uint32_t high) {
    return first >= low && (uint64_t)first + bytes <= high;
}

int r6_glsl_bindings_init(r6_glsl_bindings_view *view,
                          const void *data, size_t size) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t records, cbuffers, regions, samplers, strings;
    if (!view || !data || size < 32) {
        return R6_ERR_ARG;
    }
    r6_memset(view, 0, sizeof(*view));
    if (r6_memcmp(bytes, "R6GB", 4) != 0 ||
        r6_glsl_get16(bytes + 4) != R6_GLSL_BINDINGS_VERSION) {
        return R6_ERR_FORMAT;
    }
    records = r6_glsl_get32(bytes + 12);
    cbuffers = r6_glsl_get32(bytes + 16);
    regions = r6_glsl_get32(bytes + 20);
    samplers = r6_glsl_get32(bytes + 24);
    strings = r6_glsl_get32(bytes + 28);
    if (records < 32 || cbuffers < records || regions < cbuffers ||
        samplers < regions || strings < samplers || strings > size) {
        return R6_ERR_ARG;
    }
    if (!r6_glsl_table_ok(records, (uint64_t)r6_glsl_get32(bytes + 8) * 16u,
                          records, cbuffers)) {
        return R6_ERR_BUFFER;
    }
    view->data = bytes;
    view->size = size;
    view->count = r6_glsl_get32(bytes + 8);
    view->records = records;
    view->cbuffers = cbuffers;
    view->regions = regions;
    view->samplers = samplers;
    view->strings = strings;
    return R6_OK;
}

int r6_glsl_bindings_get_record(const r6_glsl_bindings_view *view,
                            uint32_t index, r6_glsl_bindings_record_info *out) {
    const unsigned char *at;
    uint32_t first;
    if (!view || !out || index >= view->count) {
        return R6_ERR_ARG;
    }
    at = view->data + view->records + (size_t)index * 16u;
    if (view->records + (size_t)index * 16u + 16u > view->cbuffers) {
        return R6_ERR_BUFFER;
    }
    out->flags = r6_glsl_get32(at);
    out->cbuffers = r6_glsl_get16(at + 4);
    out->samplers = r6_glsl_get16(at + 6);
    first = r6_glsl_get32(at + 8);
    out->cbuffer_first = first;
    out->name_off = r6_glsl_get32(at + 12);
    if (!r6_glsl_table_ok(first, (uint64_t)out->cbuffers * 24u,
                          view->cbuffers, view->regions) ||
        (uint64_t)out->samplers * 12u > view->strings - view->samplers ||
        !r6_glsl_bindings_name(view, out->name_off)) {
        return R6_ERR_BUFFER;
    }
    return R6_OK;
}

int r6_glsl_bindings_get_cbuffer(const r6_glsl_bindings_view *view,
                             const r6_glsl_bindings_record_info *record,
                             uint32_t index, r6_glsl_bindings_cbuffer_info *out) {
    const unsigned char *at;
    uint64_t offset;
    uint32_t first;
    if (!view || !record || !out || index >= record->cbuffers) {
        return R6_ERR_ARG;
    }
    offset = (uint64_t)record->cbuffer_first + (uint64_t)index * 24u;
    if (offset < view->cbuffers || offset + 24u > view->regions) {
        return R6_ERR_BUFFER;
    }
    at = view->data + offset;
    out->binding = r6_glsl_get32(at);
    out->name_off = r6_glsl_get32(at + 4);
    out->size = r6_glsl_get32(at + 8);
    out->slots = r6_glsl_get16(at + 12);
    out->ubo = r6_glsl_get16(at + 14);
    out->regions = r6_glsl_get16(at + 16);
    first = r6_glsl_get32(at + 20);
    out->region_first = first;
    if (!r6_glsl_table_ok(first, (uint64_t)out->regions * 8u,
                          view->regions, view->samplers) ||
        !r6_glsl_bindings_name(view, out->name_off)) {
        return R6_ERR_BUFFER;
    }
    return R6_OK;
}

int r6_glsl_bindings_region(const r6_glsl_bindings_view *view,
                            const r6_glsl_bindings_cbuffer_info *block,
                            uint32_t index, r6_glsl_manifest_region *out) {
    const unsigned char *at;
    uint64_t offset;
    if (!view || !block || !out || index >= block->regions) {
        return R6_ERR_ARG;
    }
    offset = (uint64_t)block->region_first + (uint64_t)index * 8u;
    if (offset < view->regions || offset + 8u > view->samplers) {
        return R6_ERR_BUFFER;
    }
    at = view->data + offset;
    out->offset = r6_glsl_get32(at);
    out->size = r6_glsl_get16(at + 4);
    out->kind = at[6];
    out->type = at[7];
    return R6_OK;
}

int r6_glsl_bindings_get_sampler(const r6_glsl_bindings_view *view,
                             const r6_glsl_bindings_record_info *record,
                             uint32_t index, r6_glsl_bindings_sampler_info *out) {
    const unsigned char *at;
    uint64_t offset;
    if (!view || !record || !out || index >= record->samplers) {
        return R6_ERR_ARG;
    }
    offset = (uint64_t)view->samplers + (uint64_t)index * 12u;
    if (offset + 12u > view->strings) {
        return R6_ERR_BUFFER;
    }
    at = view->data + offset;
    out->unit = r6_glsl_get32(at);
    out->texture_off = r6_glsl_get32(at + 4);
    out->sampler_off = r6_glsl_get32(at + 8);
    if (!r6_glsl_bindings_name(view, out->texture_off) ||
        !r6_glsl_bindings_name(view, out->sampler_off)) {
        return R6_ERR_BUFFER;
    }
    return R6_OK;
}

const char *r6_glsl_bindings_name(const r6_glsl_bindings_view *view,
                                  uint32_t offset) {
    size_t at;
    if (!view || offset >= view->size) {
        return NULL;
    }
    for (at = offset; at < view->size; at++) {
        if (view->data[at] == 0) {
            return (const char *)(view->data + offset);
        }
    }
    return NULL;
}
