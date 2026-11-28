/* Freestanding inventory of shipped MA61 default/custom color blocks.
 * The blob comes from tools/engine/color_block_catalog.py. Paths, line counts,
 * block names, source line numbers and verbatim numeric token bytes are
 * copied. CP932 comments, color roles, icon/library enums and float semantics
 * stay unparsed. */
#ifndef R6_COLOR_BLOCK_CATALOG_H
#define R6_COLOR_BLOCK_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_color_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t token_count;
    uint32_t vec4_max;
    uint32_t float_max;
    uint32_t int_max;
    uint32_t reserved;
} r6_color_header_t;

typedef struct r6_color_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t first_line;
    uint32_t row_base;
} r6_color_file_t;

typedef struct r6_color_row_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t line;
    uint32_t token_offset;
} r6_color_row_t;

R6_API int r6_color_parse(const void *data, size_t size,
                          r6_color_header_t *out);

R6_API int r6_color_file(const void *data, size_t size, uint32_t index,
                         r6_color_file_t *out);

R6_API int r6_color_path(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity);

R6_API int r6_color_row(const void *data, size_t size, uint32_t index,
                        r6_color_row_t *out);

R6_API int r6_color_name(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity);

R6_API int r6_color_token(const void *data, size_t size, uint32_t index,
                          uint32_t slot, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
