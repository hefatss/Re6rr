/* Freestanding inventory of shipped car vinyl blend parameter tables.
 * The blob comes from tools/engine/color_vinyl_blend_catalog.py. Path, line
 * counts, list/function names, row positions and verbatim numeric token bytes
 * are copied. CP932 comments and role meanings stay unparsed. */
#ifndef R6_COLOR_VINYL_BLEND_CATALOG_H
#define R6_COLOR_VINYL_BLEND_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_cvb_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t token_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t function_count;
    uint32_t reserved;
} r6_cvb_header_t;

typedef struct r6_cvb_row_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t line;
    uint32_t token_offset;
    uint32_t token_count;
} r6_cvb_row_t;

typedef struct r6_cvb_function_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t line;
} r6_cvb_function_t;

R6_API int r6_cvb_parse(const void *data, size_t size, r6_cvb_header_t *out);

R6_API int r6_cvb_path(const void *data, size_t size, char *out,
                       size_t capacity);

R6_API int r6_cvb_row(const void *data, size_t size, uint32_t index,
                      r6_cvb_row_t *out);

R6_API int r6_cvb_token(const void *data, size_t size, uint32_t index,
                        uint32_t slot, char *out, size_t capacity);

R6_API int r6_cvb_function(const void *data, size_t size, uint32_t index,
                           r6_cvb_function_t *out);

R6_API int r6_cvb_function_name(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
