/* Host-side GLES call layer. The core validates resources and issues calls
 * through a host-provided sink; it never links GLES or allocates memory.
 *
 * Stage, binding and texture units are numeric values from the reflected
 * manifest; the sink maps them to GL objects.
 */
#ifndef R6_GLES_H
#define R6_GLES_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"
#include "r6_glsl.h"
#include "r6_glsl_manifest.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_gles_sink {
    void *user;
    int (*shader)(void *user, uint32_t stage, const char *source, size_t size);
    int (*uniform_block)(void *user, uint32_t binding, const void *data,
                         size_t size);
    int (*texture)(void *user, uint32_t unit,
                   const r6_glsl_texture_desc *desc, const void *pixels,
                   size_t size);
    int (*draw)(void *user, uint32_t count);
} r6_gles_sink;

/* Compile one reflected stage from emitted GLSL ES 3.00 text. */
R6_API int r6_gles_emit_shader(const r6_gles_sink *sink,
                               const r6_glsl_bindings_view *view,
                               uint32_t record_index,
                               const char *source, size_t size);

/* Pack reflected UBO regions into scratch, then upload the block.
 * Regions must match the manifest order; count is region_count. */
R6_API int r6_gles_emit_uniforms(const r6_gles_sink *sink,
                                 const r6_glsl_bindings_view *view,
                                 uint32_t record_index, uint32_t cbuffer_index,
                                 void *scratch, size_t scratch_size,
                                 const r6_glsl_region *regions,
                                 const r6_glsl_value *values,
                                 uint32_t region_count);

/* Upload decoded RGBA8 pixels to a reflected sampler unit. */
R6_API int r6_gles_emit_texture(const r6_gles_sink *sink, uint32_t unit,
                                uint8_t format, uint32_t width,
                                uint32_t height, const void *pixels,
                                size_t size);

/* Pass a draw call to the sink. */
R6_API int r6_gles_emit_draw(const r6_gles_sink *sink, uint32_t count);

#ifdef __cplusplus
}
#endif

#endif
