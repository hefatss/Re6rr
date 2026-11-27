/* Freestanding inventory of shipped course route rows and path bins. The blob
 * comes from tools/engine/course_paths_catalog.py. Route `.bin` names are kept
 * exactly as shipped; duplicate basenames are not resolved to area paths and
 * no geometry values are copied. */
#ifndef R6_COURSE_PATHS_CATALOG_H
#define R6_COURSE_PATHS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_course_paths_header_t {
    uint32_t version;
    uint32_t route_count;
    uint32_t ref_count;
    uint32_t file_count;
    uint32_t strings_size;
} r6_course_paths_header_t;

typedef struct r6_course_paths_file_t {
    uint32_t file_size;
    uint32_t triple_count;
} r6_course_paths_file_t;

typedef struct r6_course_paths_route_t {
    uint32_t area_id;
    uint32_t loop;
    uint32_t camera_direction;
    uint32_t path_first;
    uint32_t path_count;
} r6_course_paths_route_t;

R6_API int r6_course_paths_parse(const void *data, size_t size,
                                 r6_course_paths_header_t *out);

R6_API int r6_course_paths_file(const void *data, size_t size, uint32_t index,
                                r6_course_paths_file_t *out);

/* Copied NUL-terminated relative path under data/course/path. */
R6_API int r6_course_paths_path(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

R6_API int r6_course_paths_route(const void *data, size_t size, uint32_t index,
                                 r6_course_paths_route_t *out);

/* Copied route MenuText and exact `.bin` name at one global ref index. */
R6_API int r6_course_paths_route_name(const void *data, size_t size,
                                      uint32_t index, char *out,
                                      size_t capacity);

R6_API int r6_course_paths_route_ref(const void *data, size_t size,
                                     uint32_t index, char *out,
                                     size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
