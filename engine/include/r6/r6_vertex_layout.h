/* Reader for the compiled R6GV vertex-input layout.
 *
 * Records carry the explicit GLSL location, DXBC semantic and component mask
 * for every non-system vertex input. The host still decides which mesh buffer
 * fills each semantic; no asset mapping is stored here.
 */
#ifndef R6_VERTEX_LAYOUT_H
#define R6_VERTEX_LAYOUT_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_VERTEX_HEADER_SIZE 24u
#define R6_VERTEX_RECORD_SIZE 16u

typedef struct r6_vertex_view {
    const unsigned char *data;
    size_t size;
    uint32_t count;
    uint32_t strings;
} r6_vertex_view;

typedef struct r6_vertex_attrib {
    uint32_t shader_off;
    uint16_t location;
    uint16_t semantic_index;
    uint16_t mask;
    uint32_t semantic_off;
} r6_vertex_attrib;

R6_API int r6_vertex_init(r6_vertex_view *view, const void *data, size_t size);

R6_API int r6_vertex_get_attrib(const r6_vertex_view *view, uint32_t index,
                                r6_vertex_attrib *out);

/* Find a shader's input at an explicit GLSL location. */
R6_API int r6_vertex_find(const r6_vertex_view *view, const char *shader,
                          uint16_t location, r6_vertex_attrib *out);

/* NUL-terminated interned name, or NULL when the offset is outside the blob. */
R6_API const char *r6_vertex_name(const r6_vertex_view *view, uint32_t offset);

#ifdef __cplusplus
}
#endif

#endif
