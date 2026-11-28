/* Freestanding inventory of shipped XMD version 0/1 stream directories.
 * The blob comes from tools/engine/xmd_v1_directory_catalog.py. Paths,
 * container sizes, version/count words, stream offsets and the first eight
 * bytes of each stream are copied; stream payloads are not parsed. */
#ifndef R6_XMD_V1_DIRECTORY_CATALOG_H
#define R6_XMD_V1_DIRECTORY_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_xmd_v1_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t stream_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_xmd_v1_header_t;

typedef struct r6_xmd_v1_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t version;
    uint32_t table_end;
    uint32_t stream_index;
    uint32_t count;
} r6_xmd_v1_file_t;

typedef struct r6_xmd_v1_stream_t {
    uint32_t offset;
    uint32_t length;
    uint8_t magic[8];
} r6_xmd_v1_stream_t;

R6_API int r6_xmd_v1_parse(const void *data, size_t size,
                           r6_xmd_v1_header_t *out);

R6_API int r6_xmd_v1_file(const void *data, size_t size, uint32_t index,
                          r6_xmd_v1_file_t *out);

R6_API int r6_xmd_v1_path(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity);

R6_API int r6_xmd_v1_stream(const void *data, size_t size, uint32_t index,
                            r6_xmd_v1_stream_t *out);

#ifdef __cplusplus
}
#endif

#endif
