/* Freestanding inventory of shipped Scene.Lua descriptor facts. The blob
 * comes from tools/engine/scene_descriptors_catalog.py. Paths, strings and
 * counts are copied; camera and scene semantics are not inferred. */
#ifndef R6_SCENE_DESCRIPTORS_CATALOG_H
#define R6_SCENE_DESCRIPTORS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_scene_descriptors_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
} r6_scene_descriptors_header_t;

typedef struct r6_scene_descriptors_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t root_offset;
    uint32_t root_length;
    uint32_t environment_offset;
    uint32_t environment_length;
    uint32_t size;
    uint32_t event_num;
    uint32_t event_count;
} r6_scene_descriptors_file_t;

R6_API int r6_scene_descriptors_parse(
    const void *data, size_t size, r6_scene_descriptors_header_t *out);

R6_API int r6_scene_descriptors_file(const void *data, size_t size,
                                     uint32_t index,
                                     r6_scene_descriptors_file_t *out);

R6_API int r6_scene_descriptors_path(const void *data, size_t size,
                                     uint32_t index, char *out,
                                     size_t capacity);

R6_API int r6_scene_descriptors_root(const void *data, size_t size,
                                     uint32_t index, char *out,
                                     size_t capacity);

R6_API int r6_scene_descriptors_environment(const void *data, size_t size,
                                            uint32_t index, char *out,
                                            size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
