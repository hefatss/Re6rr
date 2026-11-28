/* Freestanding inventory of shipped scene function names and returns.
 * The blob comes from tools/engine/scene_func_catalog.py. Paths, function
 * names and copied ASCII return expressions are stored; CP932 comments and
 * scene logic are not decoded. */
#ifndef R6_SCENE_FUNC_CATALOG_H
#define R6_SCENE_FUNC_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_scene_func_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t function_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_scene_func_header_t;

typedef struct r6_scene_func_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t function_base;
    uint32_t count;
} r6_scene_func_file_t;

typedef struct r6_scene_func_row_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t result_offset;
    uint32_t result_length;
} r6_scene_func_row_t;

R6_API int r6_scene_func_parse(const void *data, size_t size,
                               r6_scene_func_header_t *out);

R6_API int r6_scene_func_file(const void *data, size_t size, uint32_t index,
                              r6_scene_func_file_t *out);

R6_API int r6_scene_func_path(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

R6_API int r6_scene_func_row(const void *data, size_t size, uint32_t index,
                             r6_scene_func_row_t *out);

R6_API int r6_scene_func_name(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

R6_API int r6_scene_func_result(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
