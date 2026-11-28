/* Freestanding inventory of shipped DISTCLIP.lua integer table facts.
 * The blob comes from tools/engine/distclip_catalog.py. Paths, table names,
 * key names and active integer rows are copied; comment lines and clip
 * rendering behavior are not stored. */
#ifndef R6_DISTCLIP_CATALOG_H
#define R6_DISTCLIP_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_distclip_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_distclip_header_t;

typedef struct r6_distclip_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t table_offset;
    uint32_t table_length;
    uint32_t size;
    uint32_t lines;
    uint32_t row_base;
    uint32_t rows;
} r6_distclip_file_t;

typedef struct r6_distclip_row_t {
    uint32_t key_offset;
    uint32_t key_length;
    uint32_t value;
} r6_distclip_row_t;

R6_API int r6_distclip_parse(const void *data, size_t size,
                             r6_distclip_header_t *out);

R6_API int r6_distclip_file(const void *data, size_t size, uint32_t index,
                            r6_distclip_file_t *out);

R6_API int r6_distclip_path(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_distclip_table(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_distclip_row(const void *data, size_t size, uint32_t index,
                           r6_distclip_row_t *out);

R6_API int r6_distclip_row_key(const void *data, size_t size, uint32_t index,
                               char *out, size_t capacity);

R6_API int r6_distclip_row_value(const void *data, size_t size,
                                 uint32_t index, uint32_t *out);

#ifdef __cplusplus
}
#endif

#endif
