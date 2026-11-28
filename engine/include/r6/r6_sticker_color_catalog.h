/* Freestanding inventory of shipped side-sticker and vinyl color rows.
 * The blob comes from tools/engine/sticker_color_catalog.py. Paths, corpus
 * kinds, row lines, selector ids and verbatim numeric token bytes are copied.
 * CP932 color names and palette roles stay unparsed. */
#ifndef R6_STICKER_COLOR_CATALOG_H
#define R6_STICKER_COLOR_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_stc_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t side_files;
    uint32_t vinyl_files;
    uint32_t source_bytes;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t reserved;
} r6_stc_header_t;

typedef struct r6_stc_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t kind;
    uint32_t size;
    uint32_t row_base;
} r6_stc_file_t;

typedef struct r6_stc_row_t {
    uint32_t line;
    uint32_t ident;
    uint32_t token0_offset;
    uint32_t token1_offset;
    uint32_t token2_offset;
} r6_stc_row_t;

R6_API int r6_stc_parse(const void *data, size_t size, r6_stc_header_t *out);

R6_API int r6_stc_file(const void *data, size_t size, uint32_t index,
                       r6_stc_file_t *out);

R6_API int r6_stc_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

R6_API int r6_stc_row(const void *data, size_t size, uint32_t index,
                      r6_stc_row_t *out);

R6_API int r6_stc_token(const void *data, size_t size, uint32_t index,
                        uint32_t slot, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
