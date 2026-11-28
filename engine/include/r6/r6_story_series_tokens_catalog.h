/* Freestanding inventory of shipped story-series configuration token lines.
 * The blob comes from tools/engine/story_series_tokens_catalog.py. Source
 * sizes, block headers and token text before `//` comments are copied; no
 * race, story or carryover rule is inferred. */
#ifndef R6_STORY_SERIES_TOKENS_CATALOG_H
#define R6_STORY_SERIES_TOKENS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_story_series_header_t {
    uint32_t version;
    uint32_t block_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_size;
    uint32_t source_lines;
} r6_story_series_header_t;

typedef struct r6_story_series_block_t {
    uint32_t header_offset;
    uint32_t header_length;
    uint32_t lines;
} r6_story_series_block_t;

R6_API int r6_story_series_parse(const void *data, size_t size,
                                 r6_story_series_header_t *out);

R6_API int r6_story_series_block(const void *data, size_t size,
                                 uint32_t index,
                                 r6_story_series_block_t *out);

R6_API int r6_story_series_header(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity);

R6_API int r6_story_series_line(const void *data, size_t size,
                                uint32_t index, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
