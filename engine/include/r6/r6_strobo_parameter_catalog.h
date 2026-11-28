/* Freestanding inventory of shipped StroboLightOnOffParameter.lua facts.
 * The blob comes from tools/engine/strobo_parameter_catalog.py. Paths,
 * DEBUG_CODE, integer-pair rows and accessor names are copied; CP932 comments
 * and timing/rendering behavior are not decoded. */
#ifndef R6_STROBO_PARAMETER_CATALOG_H
#define R6_STROBO_PARAMETER_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_strobo_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t table_count;
    uint32_t row_count;
    uint32_t function_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_strobo_header_t;

typedef struct r6_strobo_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t debug;
    uint32_t table_base;
    uint32_t row_base;
    uint32_t function_base;
} r6_strobo_file_t;

typedef struct r6_strobo_table_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t row_base;
    uint32_t rows;
} r6_strobo_table_t;

typedef struct r6_strobo_row_t {
    uint32_t first;
    uint32_t second;
} r6_strobo_row_t;

R6_API int r6_strobo_parse(const void *data, size_t size,
                           r6_strobo_header_t *out);

R6_API int r6_strobo_file(const void *data, size_t size,
                          r6_strobo_file_t *out);

R6_API int r6_strobo_path(const void *data, size_t size, char *out,
                          size_t capacity);

R6_API int r6_strobo_table(const void *data, size_t size, uint32_t index,
                           r6_strobo_table_t *out);

R6_API int r6_strobo_table_name(const void *data, size_t size,
                                uint32_t index, char *out, size_t capacity);

R6_API int r6_strobo_row(const void *data, size_t size, uint32_t index,
                         r6_strobo_row_t *out);

R6_API int r6_strobo_function(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
