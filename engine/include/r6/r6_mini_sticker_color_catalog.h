/* Freestanding inventory of shipped mini-sticker color row shapes.
 * The blob comes from tools/engine/mini_sticker_color_catalog.py. File paths,
 * source sizes, row positions, bank indices and verbatim numeric token bytes
 * are copied. CP932 color names and bank semantics stay unparsed. */
#ifndef R6_MINI_STICKER_COLOR_CATALOG_H
#define R6_MINI_STICKER_COLOR_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_msc_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t token_count;
    uint32_t line_count;
    uint32_t vinyl_max;
    uint32_t source_bytes;
    uint32_t string_size;
    uint32_t reserved;
} r6_msc_header_t;

typedef struct r6_msc_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t size;
    uint32_t row_base;
} r6_msc_file_t;

typedef struct r6_msc_row_t {
    uint32_t line;
    uint32_t slot;
    uint32_t token0_offset;
    uint32_t token1_offset;
    uint32_t token2_offset;
} r6_msc_row_t;

R6_API int r6_msc_parse(const void *data, size_t size, r6_msc_header_t *out);

R6_API int r6_msc_file(const void *data, size_t size, uint32_t index,
                       r6_msc_file_t *out);

R6_API int r6_msc_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

R6_API int r6_msc_row(const void *data, size_t size, uint32_t index,
                      r6_msc_row_t *out);

R6_API int r6_msc_token(const void *data, size_t size, uint32_t index,
                        uint32_t slot, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
