/* Freestanding inventory of shipped NavimapParam.lua structural facts.
 * The blob comes from tools/engine/navimap_param_catalog.py. Paths, copied
 * ASCII global names and integer literals are stored; Shift-JIS comments and
 * navimap behavior are not parsed. */
#ifndef R6_NAVIMAP_PARAM_CATALOG_H
#define R6_NAVIMAP_PARAM_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_navimap_header_t {
    uint32_t version;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t source_lines;
    uint32_t scalar_count;
    uint32_t table_count;
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t table_name_offset;
    uint32_t table_name_length;
} r6_navimap_header_t;

typedef struct r6_navimap_scalar_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t value_offset;
    uint32_t value_length;
    uint32_t active;
} r6_navimap_scalar_t;

R6_API int r6_navimap_parse(const void *data, size_t size,
                            r6_navimap_header_t *out);

R6_API int r6_navimap_scalar(const void *data, size_t size, uint32_t index,
                             r6_navimap_scalar_t *out);

R6_API int r6_navimap_path(const void *data, size_t size, char *out,
                           size_t capacity);

R6_API int r6_navimap_table_name(const void *data, size_t size, char *out,
                                 size_t capacity);

R6_API int r6_navimap_scalar_name(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity);

R6_API int r6_navimap_scalar_value(const void *data, size_t size,
                                   uint32_t index, char *out,
                                   size_t capacity);

R6_API int r6_navimap_table_value(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
