/* Freestanding inventory of shipped stage LOADLIST section blocks and NDWD
 * stream descriptors. The blob comes from tools/engine/loadlist_catalog.py.
 * Stream geometry is not copied and no surface class is inferred. */
#ifndef R6_LOADLIST_CATALOG_H
#define R6_LOADLIST_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_LOADLIST_MIN_STREAM 0x50

typedef struct r6_loadlist_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t block_count;
    uint32_t stream_count;
    uint32_t strings_size;
    uint32_t reserved;
} r6_loadlist_header_t;

typedef struct r6_loadlist_file_t {
    uint32_t block_first;
    uint32_t block_count;
} r6_loadlist_file_t;

typedef struct r6_loadlist_block_t {
    uint32_t section;
    uint32_t source_size;
    uint32_t inflated_size;
    uint32_t wrapped;
    uint32_t stream_first;
    uint32_t stream_count;
} r6_loadlist_block_t;

typedef struct r6_loadlist_stream_t {
    uint32_t offset;
    uint32_t size;
} r6_loadlist_stream_t;

R6_API int r6_loadlist_parse(const void *data, size_t size,
                             r6_loadlist_header_t *out);

R6_API int r6_loadlist_file(const void *data, size_t size, uint32_t index,
                            r6_loadlist_file_t *out);

/* Copied NUL-terminated LOADLIST path. */
R6_API int r6_loadlist_path(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_loadlist_block(const void *data, size_t size, uint32_t index,
                             r6_loadlist_block_t *out);

/* Copied NUL-terminated relative path of the section's gzip or raw bin. */
R6_API int r6_loadlist_bin_path(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

R6_API int r6_loadlist_stream(const void *data, size_t size, uint32_t index,
                              r6_loadlist_stream_t *out);

/* Copied NUL-terminated ROAD_NAME label. */
R6_API int r6_loadlist_stream_name(const void *data, size_t size,
                                   uint32_t index, char *out,
                                   size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
