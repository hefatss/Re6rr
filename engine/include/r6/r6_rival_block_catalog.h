/* Freestanding inventory of shipped story-rival block facts.
 * The blob comes from tools/engine/rival_block_catalog.py. Source path,
 * ECharacter_* block names, line spans, five copied ASCII keyword rows and
 * their occurrence counts are stored. CP932 comments, float fields and rival
 * behavior are not decoded. */
#ifndef R6_RIVAL_BLOCK_CATALOG_H
#define R6_RIVAL_BLOCK_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_rival_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t block_count;
    uint32_t unique_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t lines;
} r6_rival_header_t;

typedef struct r6_rival_block_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t line_start;
    uint32_t line_count;
    uint32_t row_offset[5];
    uint32_t row_length[5];
    uint32_t count[5];
} r6_rival_block_t;

R6_API int r6_rival_parse(const void *data, size_t size,
                          r6_rival_header_t *out);

R6_API int r6_rival_path(const void *data, size_t size, char *out,
                         size_t capacity);

R6_API int r6_rival_block(const void *data, size_t size, uint32_t index,
                          r6_rival_block_t *out);

R6_API int r6_rival_name(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity);

R6_API int r6_rival_keyword(const void *data, size_t size, uint32_t index,
                            uint32_t keyword, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
