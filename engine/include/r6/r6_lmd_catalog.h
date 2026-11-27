/* Freestanding reader for gzip/XMD.001 header facts from shipped .LMD files.
 * The blob comes from tools/engine/lmd_catalog.py. Stream contents are never
 * inflated or interpreted by the core; only copied facts cross the bridge. */
#ifndef R6_LMD_CATALOG_H
#define R6_LMD_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_LMD_FILES = 985,
    R6_LMD_STREAMS_PER_FILE = 3,
    R6_LMD_XMD_HEADER = 0x30
};

typedef struct r6_lmd_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t stream_count;
    uint32_t strings_size;
} r6_lmd_header_t;

typedef struct r6_lmd_file_t {
    uint32_t compressed_size;
    uint32_t gzip_flags;
    uint32_t gzip_mtime;
    uint32_t gzip_xfl_os;
    uint32_t expected_size;
    uint32_t inflated_size;
    uint32_t xmd_version;
    uint32_t stream_first;
} r6_lmd_file_t;

R6_API int r6_lmd_parse(const void *data, size_t size, r6_lmd_header_t *out);

/* Validates the copied gzip ISIZE and XMD version against the stored layout. */
R6_API int r6_lmd_file(const void *data, size_t size, uint32_t index,
                       r6_lmd_file_t *out);

/* Copied NUL-terminated relative path from the dump. */
R6_API int r6_lmd_path(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

/* Copied XMD stream offset and size for one of the three streams. */
R6_API int r6_lmd_stream(const void *data, size_t size, uint32_t index,
                         uint32_t local, uint32_t *offset, uint32_t *size_out);

#ifdef __cplusplus
}
#endif

#endif
