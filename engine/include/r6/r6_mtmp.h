/* Freestanding reader for raw .MTMP stage-effect model tables. The blob comes
 * from tools/engine/mtmp_catalog.py. Values are copied verbatim; no transform
 * or hierarchy semantics are inferred. */
#ifndef R6_MTMP_H
#define R6_MTMP_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_mtmp_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t object_count;
    uint32_t strings_size;
} r6_mtmp_header_t;

typedef struct r6_mtmp_file_t {
    uint32_t file_size;
    uint32_t object_first;
    uint32_t object_count;
} r6_mtmp_file_t;

R6_API int r6_mtmp_parse(const void *data, size_t size,
                         r6_mtmp_header_t *out);

R6_API int r6_mtmp_file(const void *data, size_t size, uint32_t index,
                        r6_mtmp_file_t *out);

/* Copied NUL-terminated relative path from the dump. */
R6_API int r6_mtmp_path(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

/* Copied SCALE value without the `SCALE:` prefix. */
R6_API int r6_mtmp_scale(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity);

/* Copied tab-separated OBJECT fields without the `OBJECT:` prefix. */
R6_API int r6_mtmp_object(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
