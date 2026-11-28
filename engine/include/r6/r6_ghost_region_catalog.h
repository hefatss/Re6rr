/* Freestanding inventory of shipped ghost-region Lua row facts. The blob comes
 * from tools/engine/ghost_region_catalog.py. Paths, counts and literal integer
 * facts are copied; no region behaviour is inferred. */
#ifndef R6_GHOST_REGION_CATALOG_H
#define R6_GHOST_REGION_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_ghost_region_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t source_lines;
    uint32_t region_count;
    uint32_t function_count;
} r6_ghost_region_header_t;

typedef struct r6_ghost_region_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t source_size;
    uint32_t line_count;
    uint32_t region_count;
    uint32_t region_min;
    uint32_t region_max;
    uint32_t function_count;
    uint32_t defeated0;
    uint32_t defeated1;
    uint32_t defeated2;
} r6_ghost_region_file_t;

R6_API int r6_ghost_region_parse(const void *data, size_t size,
                                 r6_ghost_region_header_t *out);

R6_API int r6_ghost_region_file(const void *data, size_t size, uint32_t index,
                                r6_ghost_region_file_t *out);

R6_API int r6_ghost_region_path(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
