/* Freestanding inventory of shipped custom-frame id-to-texture rows. The blob
 * comes from tools/engine/custom_frame_catalog.py. IDs and copied names are
 * packed; texture payloads and UI semantics are not inferred. */
#ifndef R6_CUSTOM_FRAME_CATALOG_H
#define R6_CUSTOM_FRAME_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_custom_frame_header_t {
    uint32_t version;
    uint32_t row_count;
    uint32_t name_count;
    uint32_t function_count;
    uint32_t string_size;
    uint32_t source_size;
} r6_custom_frame_header_t;

typedef struct r6_custom_frame_row_t {
    uint32_t id;
    uint32_t name_offset[4];
    uint32_t name_length[4];
} r6_custom_frame_row_t;

R6_API int r6_custom_frame_parse(const void *data, size_t size,
                                 r6_custom_frame_header_t *out);

R6_API int r6_custom_frame_row(const void *data, size_t size, uint32_t index,
                               r6_custom_frame_row_t *out);

R6_API int r6_custom_frame_texture(const void *data, size_t size,
                                   uint32_t index, uint32_t slot,
                                   char *out, size_t capacity);

R6_API int r6_custom_frame_function(const void *data, size_t size,
                                    uint32_t index, char *out,
                                    size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
