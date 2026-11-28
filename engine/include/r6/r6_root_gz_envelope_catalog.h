/* Freestanding inventory of root auxiliary gzip envelopes.
 * The blob comes from tools/engine/root_gz_envelope_catalog.py. File names,
 * compressed sizes, gzip header words, CRC32/ISIZE and empty-file flags are
 * copied. Inflated payloads and setting.lua.gz are excluded. */
#ifndef R6_ROOT_GZ_ENVELOPE_CATALOG_H
#define R6_ROOT_GZ_ENVELOPE_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_root_gz_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t valid_count;
    uint32_t empty_count;
    uint32_t source_bytes;
    uint32_t string_size;
} r6_root_gz_header_t;

typedef struct r6_root_gz_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t size;
    uint32_t mtime;
    uint32_t crc32;
    uint32_t isize;
    uint32_t header_flags;
    uint32_t valid;
} r6_root_gz_file_t;

R6_API int r6_root_gz_parse(const void *data, size_t size,
                            r6_root_gz_header_t *out);

R6_API int r6_root_gz_file(const void *data, size_t size, uint32_t index,
                           r6_root_gz_file_t *out);

R6_API int r6_root_gz_name(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
