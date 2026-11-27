/* Freestanding inventory of shipped stage-effect gzip headers and inflated
 * prefixes. The blob comes from tools/engine/gz_effect_catalog.py. Payload
 * bytes stay in the host; no container semantics are inferred. */
#ifndef R6_GZ_EFFECT_CATALOG_H
#define R6_GZ_EFFECT_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_GZ_EFFECT_PREFIX_SIZE 16

typedef struct r6_gz_effect_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t flag0_count;
    uint32_t flag8_count;
    uint32_t known_count;
    uint32_t other_count;
} r6_gz_effect_header_t;

typedef struct r6_gz_effect_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t compressed_size;
    uint32_t flags;
    uint32_t mtime;
    uint32_t xfl;
    uint32_t operating_system;
    uint32_t isize;
    uint32_t inflated_size;
    uint32_t header_size;
    uint32_t prefix_length;
    unsigned char prefix[R6_GZ_EFFECT_PREFIX_SIZE];
} r6_gz_effect_file_t;

R6_API int r6_gz_effect_parse(const void *data, size_t size,
                              r6_gz_effect_header_t *out);

R6_API int r6_gz_effect_file(const void *data, size_t size, uint32_t index,
                             r6_gz_effect_file_t *out);

/* Copied NUL-terminated dump-relative path. */
R6_API int r6_gz_effect_path(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
