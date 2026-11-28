/* Freestanding inventory of stage-effect PCV float-triple tables. The blob
 * comes from tools/engine/stage_effect_catalog.py. Paths, byte spans and triple
 * counts are copied; float bit patterns are not. */
#ifndef R6_STAGE_EFFECT_CATALOG_H
#define R6_STAGE_EFFECT_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_pcv_inventory_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t total_bytes;
    uint32_t triple_count;
} r6_pcv_inventory_header_t;

typedef struct r6_pcv_inventory_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t triples;
    uint32_t stride;
} r6_pcv_inventory_file_t;

R6_API int r6_pcv_inventory_parse(const void *data, size_t size,
                                 r6_pcv_inventory_header_t *out);

R6_API int r6_pcv_inventory_file(const void *data, size_t size, uint32_t index,
                                r6_pcv_inventory_file_t *out);

R6_API int r6_pcv_inventory_path(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
