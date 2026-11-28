/* Freestanding inventory of shipped NeonColor.lua row spans.
 * The blob comes from tools/engine/neon_color_catalog.py. Path, source line
 * numbers, row positions, verbatim numeric token bytes and comment presence
 * are copied. CP932 comment text, index order and fallback behavior stay
 * unparsed. */
#ifndef R6_NEON_COLOR_CATALOG_H
#define R6_NEON_COLOR_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_neon_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t comment_rows;
    uint32_t reserved;
    uint32_t path_offset;
    uint32_t path_length;
} r6_neon_header_t;

typedef struct r6_neon_row_t {
    uint32_t token_offset[3];
    uint32_t token_length[3];
    uint32_t has_comment;
    uint32_t line;
} r6_neon_row_t;

R6_API int r6_neon_parse(const void *data, size_t size, r6_neon_header_t *out);

R6_API int r6_neon_path(const void *data, size_t size, char *out,
                        size_t capacity);

R6_API int r6_neon_row(const void *data, size_t size, uint32_t index,
                       r6_neon_row_t *out);

R6_API int r6_neon_token(const void *data, size_t size, uint32_t index,
                         uint32_t slot, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
