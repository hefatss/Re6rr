/* Freestanding inventory of shipped stage-effect filename lists. The blob
 * comes from tools/engine/stage_effect_filename_lists_catalog.py. Paths and
 * ASCII .lua basenames are copied; no effect behavior is inferred. */
#ifndef R6_STAGE_EFFECT_FILENAME_LISTS_CATALOG_H
#define R6_STAGE_EFFECT_FILENAME_LISTS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_stage_effect_filename_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t name_count;
    uint32_t string_size;
} r6_stage_effect_filename_header_t;

typedef struct r6_stage_effect_filename_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t names;
} r6_stage_effect_filename_file_t;

R6_API int r6_stage_effect_filename_parse(
    const void *data, size_t size, r6_stage_effect_filename_header_t *out);

R6_API int r6_stage_effect_filename_file(
    const void *data, size_t size, uint32_t index,
    r6_stage_effect_filename_file_t *out);

R6_API int r6_stage_effect_filename_path(const void *data, size_t size,
                                         uint32_t index, char *out,
                                         size_t capacity);

R6_API int r6_stage_effect_filename_name(const void *data, size_t size,
                                         uint32_t index, char *out,
                                         size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
