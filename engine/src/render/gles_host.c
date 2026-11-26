/* Validate reflected resources and forward GLES work to a host sink. */

#include "core/internal.h"
#include "r6/r6_gles.h"

static const char gles_version[] = "#version 300 es\n";

static int gles_sink_valid(const r6_gles_sink *sink) {
    return sink && sink->shader && sink->uniform_block &&
           sink->texture && sink->draw;
}

int r6_gles_emit_shader(const r6_gles_sink *sink,
                        const r6_glsl_bindings_view *view,
                        uint32_t record_index, const char *source,
                        size_t size) {
    r6_glsl_bindings_record_info record;
    uint32_t stage;
    if (!gles_sink_valid(sink) || !view || !source ||
        size <= sizeof(gles_version) - 1u ||
        r6_memcmp(source, gles_version, sizeof(gles_version) - 1u) != 0 ||
        r6_glsl_bindings_get_record(view, record_index, &record) != R6_OK) {
        return R6_ERR_ARG;
    }
    stage = (record.flags & 1u) ? R6_GLSL_STAGE_PIXEL : R6_GLSL_STAGE_VERTEX;
    return sink->shader(sink->user, stage, source, size);
}

int r6_gles_emit_uniforms(const r6_gles_sink *sink,
                          const r6_glsl_bindings_view *view,
                          uint32_t record_index, uint32_t cbuffer_index,
                          void *scratch, size_t scratch_size,
                          const r6_glsl_region *regions,
                          const r6_glsl_value *values, uint32_t region_count) {
    r6_glsl_bindings_record_info record;
    r6_glsl_bindings_cbuffer_info block;
    r6_glsl_manifest_region reflected;
    size_t written = 0;
    uint32_t i;
    if (!gles_sink_valid(sink) || !view || !scratch || !regions || !values ||
        r6_glsl_bindings_get_record(view, record_index, &record) != R6_OK ||
        r6_glsl_bindings_get_cbuffer(view, &record, cbuffer_index,
                                     &block) != R6_OK || !block.ubo ||
        region_count != block.regions) {
        return R6_ERR_ARG;
    }
    for (i = 0; i < region_count; i++) {
        if (r6_glsl_bindings_region(view, &block, i, &reflected) != R6_OK ||
            regions[i].offset != reflected.offset ||
            regions[i].size != reflected.size ||
            regions[i].kind != reflected.kind ||
            regions[i].type != reflected.type) {
            return R6_ERR_FORMAT;
        }
    }
    if (r6_glsl_pack_ubo(scratch, scratch_size, regions, values, region_count,
                         &written) != R6_OK) {
        return R6_ERR_BUFFER;
    }
    return sink->uniform_block(sink->user, block.binding, scratch, written);
}

int r6_gles_emit_texture(const r6_gles_sink *sink, uint32_t unit,
                         uint8_t format, uint32_t width, uint32_t height,
                         const void *pixels, size_t size) {
    r6_glsl_texture_desc desc;
    int rc = r6_glsl_texture_upload(unit, format, width, height, &desc);
    if (!gles_sink_valid(sink) || !pixels) {
        return R6_ERR_ARG;
    }
    if (rc != R6_OK) {
        return rc;
    }
    if (size < desc.size) {
        return R6_ERR_BUFFER;
    }
    return sink->texture(sink->user, unit, &desc, pixels, desc.size);
}

int r6_gles_emit_draw(const r6_gles_sink *sink, uint32_t count) {
    if (!gles_sink_valid(sink)) {
        return R6_ERR_ARG;
    }
    return sink->draw(sink->user, count);
}
