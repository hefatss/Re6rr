/* Freestanding inventory of fixed-stride default ghost record tables. The
 * blob comes from tools/engine/default_ghost_catalog.py. Paths, counts, code
 * words and name-length ranges are copied; ghost names, ids and trajectory
 * words are not. */
#ifndef R6_DEFAULT_GHOST_CATALOG_H
#define R6_DEFAULT_GHOST_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_default_ghost_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t stride;
    uint32_t name1_offset;
    uint32_t name1_capacity;
    uint32_t name2_offset;
    uint32_t name2_capacity;
    uint32_t tuple_a_offset;
    uint32_t tuple_b_offset;
    uint32_t record_count;
} r6_default_ghost_header_t;

typedef struct r6_default_ghost_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t file_size;
    uint32_t record_count;
    uint32_t code;
    uint32_t name1_min;
    uint32_t name1_max;
    uint32_t name2_min;
    uint32_t name2_max;
    uint32_t tuple_a_count;
    uint32_t tuple_b_count;
} r6_default_ghost_file_t;

R6_API int r6_default_ghost_parse(const void *data, size_t size,
                                  r6_default_ghost_header_t *out);

R6_API int r6_default_ghost_file(const void *data, size_t size, uint32_t index,
                                 r6_default_ghost_file_t *out);

/* Copied dump-relative .bin path. */
R6_API int r6_default_ghost_path(const void *data, size_t size, uint32_t index,
                                 char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
