/* Freestanding inventory of fixed-stride street-lamp record tables. The blob
 * comes from tools/engine/street_lamp_catalog.py. Paths, sizes, record counts
 * and u32 flag ranges are copied; coordinate floats are not. */
#ifndef R6_STREET_LAMP_CATALOG_H
#define R6_STREET_LAMP_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_street_lamp_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t total_bytes;
    uint32_t record_count;
    uint32_t stride;
} r6_street_lamp_header_t;

typedef struct r6_street_lamp_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t record_count;
    uint32_t stride;
    uint32_t flag_min;
    uint32_t flag_max;
    uint32_t distinct;
} r6_street_lamp_file_t;

R6_API int r6_street_lamp_parse(const void *data, size_t size,
                                r6_street_lamp_header_t *out);

R6_API int r6_street_lamp_file(const void *data, size_t size, uint32_t index,
                               r6_street_lamp_file_t *out);

R6_API int r6_street_lamp_path(const void *data, size_t size, uint32_t index,
                               char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
