/* Freestanding 16-byte record inventory of the shipped hints.dat. The blob
 * comes from tools/engine/hints_catalog.py. Opaque words are copied verbatim;
 * no hint text or meaning is inferred. */
#ifndef R6_HINTS_CATALOG_H
#define R6_HINTS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_hints_header_t {
    uint32_t version;
    uint32_t record_count;
    uint32_t stride;
    uint32_t source_size;
    uint32_t distinct;
} r6_hints_header_t;

typedef struct r6_hints_row_t {
    uint32_t words[4];
} r6_hints_row_t;

R6_API int r6_hints_parse(const void *data, size_t size,
                          r6_hints_header_t *out);

R6_API int r6_hints_row(const void *data, size_t size, uint32_t index,
                        r6_hints_row_t *out);

#ifdef __cplusplus
}
#endif

#endif
