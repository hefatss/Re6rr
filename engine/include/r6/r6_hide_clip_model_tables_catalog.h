/* Freestanding inventory of shipped WANGAN hide-clip model-name tables.
 * The blob comes from tools/engine/hide_clip_model_tables_catalog.py. Paths,
 * sizes, timestamps, table names and ASCII model names are copied; clip
 * timing, render state and geometry are not inferred. */
#ifndef R6_HIDE_CLIP_MODEL_TABLES_CATALOG_H
#define R6_HIDE_CLIP_MODEL_TABLES_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_hide_clip_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t name_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t line_count;
    uint32_t table_count;
} r6_hide_clip_header_t;

typedef struct r6_hide_clip_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t table_offset;
    uint32_t table_length;
    uint32_t timestamp_offset;
    uint32_t timestamp_length;
    uint32_t size;
    uint32_t lines;
    uint32_t names;
} r6_hide_clip_file_t;

R6_API int r6_hide_clip_parse(const void *data, size_t size,
                              r6_hide_clip_header_t *out);

R6_API int r6_hide_clip_file(const void *data, size_t size, uint32_t index,
                             r6_hide_clip_file_t *out);

R6_API int r6_hide_clip_path(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_hide_clip_table(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

R6_API int r6_hide_clip_timestamp(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity);

R6_API int r6_hide_clip_name(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
