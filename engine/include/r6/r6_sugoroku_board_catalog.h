/* Freestanding inventory of shipped ghost-expedition sugoroku table facts.
 * The blob comes from tools/engine/sugoroku_board_catalog.py. Category ranges,
 * page square-type counts, reward counts and function names are copied; no
 * gameplay rules or item meanings are inferred. */
#ifndef R6_SUGOROKU_BOARD_CATALOG_H
#define R6_SUGOROKU_BOARD_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_sugoroku_header_t {
    uint32_t version;
    uint32_t category_count;
    uint32_t stage_count;
    uint32_t page_count;
    uint32_t function_count;
    uint32_t item_count;
    uint32_t square_count;
    uint32_t string_size;
} r6_sugoroku_header_t;

typedef struct r6_sugoroku_category_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t groups;
    uint32_t ids;
    uint32_t id_min;
    uint32_t id_max;
} r6_sugoroku_category_t;

typedef struct r6_sugoroku_page_t {
    uint32_t stage;
    uint32_t page;
    uint32_t squares;
    uint32_t tokens[7];
    uint32_t rewards[6];
} r6_sugoroku_page_t;

R6_API int r6_sugoroku_parse(const void *data, size_t size,
                             r6_sugoroku_header_t *out);

R6_API int r6_sugoroku_category(const void *data, size_t size, uint32_t index,
                                r6_sugoroku_category_t *out);

R6_API int r6_sugoroku_page(const void *data, size_t size, uint32_t index,
                            r6_sugoroku_page_t *out);

R6_API int r6_sugoroku_function(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
