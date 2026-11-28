/* Freestanding inventory of shipped related-section integer rows. The blob
 * comes from tools/engine/related_section_catalog.py. Paths, file sizes,
 * LOAD_SPEED integers and raw six-integer row pairs are copied; section ids
 * carry no assigned meaning. */
#ifndef R6_RELATED_SECTION_CATALOG_H
#define R6_RELATED_SECTION_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_related_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t pair_count;
    uint32_t load_speed_0;
    uint32_t load_speed_1;
} r6_related_header_t;

typedef struct r6_related_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t pairs;
    uint32_t load_speed_0;
    uint32_t load_speed_1;
} r6_related_file_t;

typedef struct r6_related_pair_t {
    uint32_t values[12];
} r6_related_pair_t;

R6_API int r6_related_parse(const void *data, size_t size,
                            r6_related_header_t *out);

R6_API int r6_related_file(const void *data, size_t size, uint32_t index,
                           r6_related_file_t *out);

R6_API int r6_related_path(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity);

R6_API int r6_related_pair(const void *data, size_t size, uint32_t index,
                           r6_related_pair_t *out);

#ifdef __cplusplus
}
#endif

#endif
