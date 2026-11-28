/* Freestanding inventory of shipped TireInfo.lua names and enums.
 * The blob comes from tools/engine/tire_model_catalog.py. Paths, TIRE_* model
 * names, WHEEL_SCALE and TIRE_WIDTH_SCALE tokens, wheel_default strings and
 * wheel_color integers are copied. Float fields and CP932 comments are not
 * decoded. */
#ifndef R6_TIRE_MODEL_CATALOG_H
#define R6_TIRE_MODEL_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_tire_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t span_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_tire_header_t;

typedef struct r6_tire_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t span_base;
    uint32_t default_offset;
    uint32_t default_length;
    uint32_t color;
} r6_tire_file_t;

typedef struct r6_tire_span_t {
    uint32_t offset;
    uint32_t length;
} r6_tire_span_t;

R6_API int r6_tire_parse(const void *data, size_t size,
                         r6_tire_header_t *out);

R6_API int r6_tire_file(const void *data, size_t size, uint32_t index,
                        r6_tire_file_t *out);

R6_API int r6_tire_path(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

R6_API int r6_tire_span(const void *data, size_t size, uint32_t index,
                        r6_tire_span_t *out);

R6_API int r6_tire_text(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

R6_API int r6_tire_default(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
