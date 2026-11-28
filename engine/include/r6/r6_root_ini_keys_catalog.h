/* Freestanding inventory of root INI section/key structure.
 * The blob comes from tools/engine/root_ini_keys_catalog.py. Only section
 * names, key names, line positions, value-presence flags and section indices
 * are copied. Raw values, including identifiers, stay uncopied. */
#ifndef R6_ROOT_INI_KEYS_CATALOG_H
#define R6_ROOT_INI_KEYS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_ini_keys_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_ini_keys_header_t;

typedef struct r6_ini_keys_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t line_base;
} r6_ini_keys_file_t;

typedef struct r6_ini_keys_line_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t kind;
    uint32_t line;
    uint32_t value_present;
    uint32_t section;
} r6_ini_keys_line_t;

R6_API int r6_ini_keys_parse(const void *data, size_t size,
                             r6_ini_keys_header_t *out);

R6_API int r6_ini_keys_file(const void *data, size_t size, uint32_t index,
                            r6_ini_keys_file_t *out);

R6_API int r6_ini_keys_path(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_ini_keys_line(const void *data, size_t size, uint32_t index,
                            r6_ini_keys_line_t *out);

R6_API int r6_ini_keys_name(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
