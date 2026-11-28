/* Freestanding inventory of shipped introductory-motion file/wait facts.
 * The blob comes from tools/engine/introductory_motions_catalog.py. Names,
 * waits and accessor names are copied; no motion payload is interpreted. */
#ifndef R6_INTRODUCTORY_MOTIONS_CATALOG_H
#define R6_INTRODUCTORY_MOTIONS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_introductory_header_t {
    uint32_t version;
    uint32_t row_count;
    uint32_t name_count;
    uint32_t function_count;
    uint32_t string_size;
    uint32_t start_frame;
    uint32_t blank_frame;
} r6_introductory_header_t;

typedef struct r6_introductory_row_t {
    uint32_t left_offset;
    uint32_t left_length;
    uint32_t right_offset;
    uint32_t right_length;
    uint32_t wait;
} r6_introductory_row_t;

R6_API int r6_introductory_parse(const void *data, size_t size,
                                 r6_introductory_header_t *out);

R6_API int r6_introductory_row(const void *data, size_t size, uint32_t index,
                               r6_introductory_row_t *out);

R6_API int r6_introductory_name(const void *data, size_t size, uint32_t index,
                                uint32_t slot, char *out, size_t capacity);

R6_API int r6_introductory_function(const void *data, size_t size,
                                    uint32_t index, char *out,
                                    size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
