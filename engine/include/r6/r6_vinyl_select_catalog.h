/* Freestanding inventory of shipped vinyl selector row shapes.
 * The blob comes from tools/engine/vinyl_select_catalog.py. Paths, selector
 * IDs, row lines and verbatim numeric value tokens are copied. CP932 labels
 * and selection roles stay unparsed. */
#ifndef R6_VINYL_SELECT_CATALOG_H
#define R6_VINYL_SELECT_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_vsl_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t source_bytes;
    uint32_t line_count;
    uint32_t id_min;
    uint32_t id_max;
    uint32_t string_size;
    uint32_t reserved;
} r6_vsl_header_t;

typedef struct r6_vsl_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t size;
    uint32_t row_base;
} r6_vsl_file_t;

typedef struct r6_vsl_row_t {
    uint32_t line;
    uint32_t ident;
    uint32_t value_offset;
} r6_vsl_row_t;

R6_API int r6_vsl_parse(const void *data, size_t size, r6_vsl_header_t *out);

R6_API int r6_vsl_file(const void *data, size_t size, uint32_t index,
                       r6_vsl_file_t *out);

R6_API int r6_vsl_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

R6_API int r6_vsl_row(const void *data, size_t size, uint32_t index,
                      r6_vsl_row_t *out);

R6_API int r6_vsl_value(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
