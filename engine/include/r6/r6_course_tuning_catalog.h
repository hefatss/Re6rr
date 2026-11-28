/* Freestanding inventory of shipped course tuning integer maps.
 * The blob comes from tools/engine/course_tuning_catalog.py. Ordinal integers
 * and copied ASCII GID/ramp/stage symbol names are stored; CP932 header
 * comments and tuning behavior are not decoded. */
#ifndef R6_COURSE_TUNING_CATALOG_H
#define R6_COURSE_TUNING_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_course_tuning_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t ramp_rows;
    uint32_t ta_rows;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_course_tuning_header_t;

typedef struct r6_course_tuning_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t global_offset;
    uint32_t global_length;
    uint32_t row_base;
    uint32_t rows;
} r6_course_tuning_file_t;

typedef struct r6_course_tuning_ramp_row_t {
    uint32_t normal;
    uint32_t extreme;
    uint32_t gid_offset;
    uint32_t gid_length;
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t alias_offset;
    uint32_t alias_length;
} r6_course_tuning_ramp_row_t;

typedef struct r6_course_tuning_ta_row_t {
    uint32_t value;
    uint32_t gid_offset;
    uint32_t gid_length;
    uint32_t name_offset;
    uint32_t name_length;
} r6_course_tuning_ta_row_t;

R6_API int r6_course_tuning_parse(const void *data, size_t size,
                                  r6_course_tuning_header_t *out);

R6_API int r6_course_tuning_file(const void *data, size_t size,
                                 uint32_t index,
                                 r6_course_tuning_file_t *out);

R6_API int r6_course_tuning_path(const void *data, size_t size,
                                 uint32_t index, char *out, size_t capacity);

R6_API int r6_course_tuning_global(const void *data, size_t size,
                                   uint32_t index, char *out,
                                   size_t capacity);

R6_API int r6_course_tuning_ramp_row(const void *data, size_t size,
                                     uint32_t index,
                                     r6_course_tuning_ramp_row_t *out);

R6_API int r6_course_tuning_ta_row(const void *data, size_t size,
                                   uint32_t index,
                                   r6_course_tuning_ta_row_t *out);

R6_API int r6_course_tuning_ramp_gid(const void *data, size_t size,
                                     uint32_t index, char *out,
                                     size_t capacity);

R6_API int r6_course_tuning_ramp_name(const void *data, size_t size,
                                      uint32_t index, char *out,
                                      size_t capacity);

R6_API int r6_course_tuning_ramp_alias(const void *data, size_t size,
                                       uint32_t index, char *out,
                                       size_t capacity);

R6_API int r6_course_tuning_ta_gid(const void *data, size_t size,
                                   uint32_t index, char *out,
                                   size_t capacity);

R6_API int r6_course_tuning_ta_name(const void *data, size_t size,
                                    uint32_t index, char *out,
                                    size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
