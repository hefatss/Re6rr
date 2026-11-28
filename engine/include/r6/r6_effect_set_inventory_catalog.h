/* Freestanding inventory of shipped stage-effect SET_*.lua path/model rows.
 * The blob comes from tools/engine/effect_set_inventory_catalog.py. Source
 * paths, set names, num/EffectSetNum tokens and copied path/model strings are
 * stored; float, transform and timing fields are not copied. */
#ifndef R6_EFFECT_SET_INVENTORY_CATALOG_H
#define R6_EFFECT_SET_INVENTORY_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_effect_set_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_effect_set_header_t;

typedef struct r6_effect_set_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t num_offset;
    uint32_t num_length;
    uint32_t effect_num_offset;
    uint32_t effect_num_length;
    uint32_t size;
    uint32_t rows;
    uint32_t row_base;
} r6_effect_set_file_t;

typedef struct r6_effect_set_row_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t model_offset;
    uint32_t model_length;
} r6_effect_set_row_t;

R6_API int r6_effect_set_parse(const void *data, size_t size,
                               r6_effect_set_header_t *out);

R6_API int r6_effect_set_file(const void *data, size_t size, uint32_t index,
                              r6_effect_set_file_t *out);

R6_API int r6_effect_set_path(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

R6_API int r6_effect_set_name(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

R6_API int r6_effect_set_num(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_effect_set_effect_num(const void *data, size_t size,
                                    uint32_t index, char *out,
                                    size_t capacity);

R6_API int r6_effect_set_row(const void *data, size_t size, uint32_t index,
                             r6_effect_set_row_t *out);

R6_API int r6_effect_set_row_path(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity);

R6_API int r6_effect_set_row_model(const void *data, size_t size,
                                   uint32_t index, char *out,
                                   size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
