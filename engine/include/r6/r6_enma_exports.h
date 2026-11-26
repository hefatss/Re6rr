/* Freestanding reader for the 172 exported symbol names of the shipped Enma
 * DLL. The derived blob comes from tools/engine/enma_exports_catalog.py. */
#ifndef R6_ENMA_EXPORTS_H
#define R6_ENMA_EXPORTS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_ENMA_EXPORT_COUNT = 172,
    R6_ENMA_EXPORT_NAME_CAP = 0x80
};

typedef struct r6_enma_exports_header {
    uint32_t count;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_enma_exports_header;

R6_API int r6_enma_exports_parse(const void *data, size_t size,
                                 r6_enma_exports_header *out);

R6_API int r6_enma_exports_name(const void *data, size_t size, uint32_t index,
                                char *name, size_t capacity);

R6_API int r6_enma_exports_find(const void *data, size_t size,
                                const char *name, uint32_t *index);

#ifdef __cplusplus
}
#endif

#endif
