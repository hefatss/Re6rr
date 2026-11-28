/* Freestanding inventory of AMCUS INI section/key structure.
 * The blob comes from tools/engine/amcus_ini_keys_catalog.py. Only section
 * names, key names, line kinds, line positions, value-presence flags and
 * section indices are copied. Values and CP932 comments stay uncopied. */
#ifndef R6_AMCUS_INI_KEYS_CATALOG_H
#define R6_AMCUS_INI_KEYS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_amcus_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t section_count;
    uint32_t key_count;
    uint32_t comment_count;
    uint32_t blank_count;
    uint32_t reserved;
} r6_amcus_header_t;

typedef struct r6_amcus_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t line_base;
} r6_amcus_file_t;

typedef struct r6_amcus_line_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t kind;
    uint32_t line;
    uint32_t value_present;
    uint32_t section;
} r6_amcus_line_t;

R6_API int r6_amcus_parse(const void *data, size_t size,
                          r6_amcus_header_t *out);

R6_API int r6_amcus_file(const void *data, size_t size, uint32_t index,
                         r6_amcus_file_t *out);

R6_API int r6_amcus_path(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity);

R6_API int r6_amcus_line(const void *data, size_t size, uint32_t index,
                         r6_amcus_line_t *out);

R6_API int r6_amcus_name(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
