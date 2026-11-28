/* Freestanding inventory of shipped setting_default.lua rows.
 * The blob comes from tools/engine/setting_default_catalog.py. Paths, m_*
 * row names, active flags, SettingConst tokens and hex literals are copied.
 * Japanese comments and setting behavior are not decoded. */
#ifndef R6_SETTING_DEFAULT_CATALOG_H
#define R6_SETTING_DEFAULT_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_setting_default_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t lines;
} r6_setting_default_header_t;

typedef struct r6_setting_default_row_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t value_offset;
    uint32_t value_length;
    uint32_t active;
} r6_setting_default_row_t;

R6_API int r6_setting_default_parse(const void *data, size_t size,
                                    r6_setting_default_header_t *out);

R6_API int r6_setting_default_path(const void *data, size_t size, char *out,
                                   size_t capacity);

R6_API int r6_setting_default_row(const void *data, size_t size,
                                  uint32_t index,
                                  r6_setting_default_row_t *out);

R6_API int r6_setting_default_name(const void *data, size_t size,
                                   uint32_t index, char *out,
                                   size_t capacity);

R6_API int r6_setting_default_value(const void *data, size_t size,
                                    uint32_t index, char *out,
                                    size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
