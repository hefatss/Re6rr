/* Freestanding inventory of shipped .nut file-level NTWD/NTLX headers. The
 * blob comes from tools/engine/nut_file_catalog.py. Paths and copied header
 * words cross the bridge; texture payloads and pixel data do not. */
#ifndef R6_NUT_FILE_CATALOG_H
#define R6_NUT_FILE_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_nut_file_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint64_t source_bytes;
    uint64_t inflated_bytes;
    uint32_t gzip_count;
    uint32_t exact_count;
} r6_nut_file_header_t;

typedef struct r6_nut_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t source_size;
    uint32_t inflated_size;
    uint32_t compressed;
    uint32_t container;
    uint32_t version;
    uint32_t entries;
    uint32_t total_lo;
    uint32_t total_hi;
    uint32_t payload_size;
    uint32_t descriptor_size;
    uint32_t packed0;
    uint32_t packed1;
    uint32_t gidx_lo;
    uint32_t gidx_hi;
    uint32_t payload_offset_lo;
    uint32_t payload_offset_hi;
    uint32_t exact;
} r6_nut_file_t;

R6_API int r6_nut_file_parse(const void *data, size_t size,
                             r6_nut_file_header_t *out);

R6_API int r6_nut_file(const void *data, size_t size, uint32_t index,
                       r6_nut_file_t *out);

/* Copied dump-relative .nut path. */
R6_API int r6_nut_file_path(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
