/* Freestanding reader for the raw RESOURCE:NU header prefixes of shipped
 * .ACT effect actors. The blob comes from tools/engine/act_headers_catalog.py;
 * no section, actor or animation semantics are inferred. */
#ifndef R6_ACT_HEADERS_H
#define R6_ACT_HEADERS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_ACT_PREFIX_SIZE 64

typedef struct r6_act_header {
    uint32_t version;
    uint32_t count;
    uint32_t prefix_size;
    uint32_t strings_size;
} r6_act_header;

R6_API int r6_act_parse(const void *data, size_t size, r6_act_header *out);

/* Copied file size for one row. */
R6_API int r6_act_size(const void *data, size_t size, uint32_t index,
                       uint32_t *file_size);

/* Copied NUL-terminated relative path from the dump. */
R6_API int r6_act_path(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

/* Copied first 64 bytes of the shipped file. */
R6_API int r6_act_prefix(const void *data, size_t size, uint32_t index,
                         unsigned char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
