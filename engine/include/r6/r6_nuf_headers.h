/* Freestanding reader for the raw 64-byte prefixes of shipped .NUF fonts.
 * The blob comes from tools/engine/nuf_headers_catalog.py. Glyph tables and
 * font layout are not interpreted. */
#ifndef R6_NUF_HEADERS_H
#define R6_NUF_HEADERS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_NUF_PREFIX_SIZE 64

typedef struct r6_nuf_header_t {
    uint32_t version;
    uint32_t count;
    uint32_t prefix_size;
    uint32_t strings_size;
} r6_nuf_header_t;

R6_API int r6_nuf_parse(const void *data, size_t size, r6_nuf_header_t *out);

/* Copied file size for one row. */
R6_API int r6_nuf_size(const void *data, size_t size, uint32_t index,
                       uint32_t *file_size);

/* Copied NUL-terminated relative path from the dump. */
R6_API int r6_nuf_path(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

/* Copied first 64 shipped bytes; magic is NUF\0 or NFH\0. */
R6_API int r6_nuf_prefix(const void *data, size_t size, uint32_t index,
                         unsigned char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
