/* Freestanding inventory of shipped Zenichi name-plate table rows. The blob
 * comes from tools/engine/zenichi_config_catalog.py. IDs, integer fields and
 * texture names are copied; no title or reward semantics are inferred. */
#ifndef R6_ZENICHI_CONFIG_CATALOG_H
#define R6_ZENICHI_CONFIG_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_zenichi_header_t {
    uint32_t version;
    uint32_t row_count;
    uint32_t string_size;
    uint32_t source_size;
} r6_zenichi_header_t;

typedef struct r6_zenichi_row_t {
    uint32_t item;
    uint32_t variation;
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t layout;
} r6_zenichi_row_t;

R6_API int r6_zenichi_parse(const void *data, size_t size,
                            r6_zenichi_header_t *out);

R6_API int r6_zenichi_row(const void *data, size_t size, uint32_t index,
                          r6_zenichi_row_t *out);

R6_API int r6_zenichi_find_id(const void *data, size_t size, uint32_t item,
                              r6_zenichi_row_t *out);

R6_API int r6_zenichi_name(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
