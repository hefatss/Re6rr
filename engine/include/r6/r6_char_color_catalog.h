/* Freestanding inventory of shipped charCar default color blocks.
 * The blob comes from tools/engine/char_color_catalog.py. Paths, source sizes,
 * COLOR_MAX, block names, row positions and verbatim numeric token bytes are
 * copied. CP932 comments, color roles and enum meanings stay unparsed. */
#ifndef R6_CHAR_COLOR_CATALOG_H
#define R6_CHAR_COLOR_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_ccc_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t token_count;
    uint32_t line_count;
    uint32_t source_bytes;
    uint32_t string_size;
    uint32_t max_one;
    uint32_t max_six;
    uint32_t max_three;
    uint32_t reserved;
} r6_ccc_header_t;

typedef struct r6_ccc_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t size;
    uint32_t lines;
    uint32_t color_max;
    uint32_t start_line;
    uint32_t row_base;
    uint32_t block_lines;
} r6_ccc_file_t;

typedef struct r6_ccc_row_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t line;
    uint32_t token_offset;
} r6_ccc_row_t;

R6_API int r6_ccc_parse(const void *data, size_t size, r6_ccc_header_t *out);

R6_API int r6_ccc_file(const void *data, size_t size, uint32_t index,
                       r6_ccc_file_t *out);

R6_API int r6_ccc_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

R6_API int r6_ccc_row(const void *data, size_t size, uint32_t index,
                      r6_ccc_row_t *out);

R6_API int r6_ccc_token(const void *data, size_t size, uint32_t index,
                        uint32_t slot, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
