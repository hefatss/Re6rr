/* Freestanding reader for the 16 recovered Enma enum domains. The derived
 * blob comes from tools/engine/enma_enum_catalog.py. */
#ifndef R6_ENMA_ENUMS_H
#define R6_ENMA_ENUMS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_ENMA_ENUM_COUNT = 16,
    R6_ENMA_ENUM_NAME_CAP = 0x80
};

typedef struct r6_enma_enum_header {
    uint32_t count;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_enma_enum_header;

R6_API int r6_enma_enum_parse(const void *data, size_t size,
                              r6_enma_enum_header *out);

R6_API int r6_enma_enum_name(const void *data, size_t size, uint32_t index,
                             char *name, size_t capacity);

R6_API int r6_enma_enum_count(const void *data, size_t size, uint32_t index,
                              uint32_t *count);

R6_API int r6_enma_enum_value(const void *data, size_t size, uint32_t index,
                              uint32_t ordinal, uint32_t *value, char *name,
                              size_t capacity);

R6_API int r6_enma_enum_find(const void *data, size_t size, uint32_t index,
                             uint32_t value, char *name, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
