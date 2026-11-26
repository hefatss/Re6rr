/* Freestanding reader for the recovered unlock/honor-condition schema. The
 * derived blob comes from tools/engine/honor_schema_catalog.py. No per-episode
 * predicate instances are implied. */
#ifndef R6_HONOR_SCHEMA_H
#define R6_HONOR_SCHEMA_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_HONOR_TYPES = 13,
    R6_HONOR_FIELD_MAX = 5,
    R6_HONOR_NAME_CAP = 0x80
};

typedef struct r6_honor_schema_header {
    uint32_t type_count;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_honor_schema_header;

R6_API int r6_honor_schema_parse(const void *data, size_t size,
                                 r6_honor_schema_header *out);

R6_API int r6_honor_schema_type(const void *data, size_t size, uint32_t type,
                                char *name, size_t capacity,
                                uint32_t *field_count);

R6_API int r6_honor_schema_field(const void *data, size_t size, uint32_t type,
                                 uint32_t field, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
