/* Freestanding reader for recovered Enma SetDefault constant writes. The
 * derived blob comes from tools/engine/enma_defaults_catalog.py. */
#ifndef R6_ENMA_DEFAULTS_H
#define R6_ENMA_DEFAULTS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_ENMA_DEFAULT_STRUCTS = 32,
    R6_ENMA_DEFAULT_NAME_CAP = 0x80
};

typedef struct r6_enma_defaults_header {
    uint32_t count;
    uint32_t fields_off;
    uint32_t data_off;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_enma_defaults_header;

R6_API int r6_enma_defaults_parse(const void *data, size_t size,
                                  r6_enma_defaults_header *out);

R6_API int r6_enma_defaults_struct(const void *data, size_t size,
                                   uint32_t index, char *name,
                                   size_t capacity, uint32_t *max_written,
                                   uint32_t *field_count);

R6_API int r6_enma_defaults_field(const void *data, size_t size,
                                  uint32_t index, uint32_t field,
                                  uint32_t *offset, uint32_t *byte_count,
                                  void *bytes, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
