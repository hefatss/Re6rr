/* Freestanding inventory of shipped root INI section/key/value facts.
 * The blob comes from tools/engine/root_ini_catalog.py. Paths, sections,
 * keys, values and `;` comments are copied; device/card/online behavior is
 * not inferred. */
#ifndef R6_ROOT_INI_CATALOG_H
#define R6_ROOT_INI_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_root_ini_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t key_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t comment_count;
} r6_root_ini_header_t;

typedef struct r6_root_ini_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t section_offset;
    uint32_t section_length;
    uint32_t key_base;
    uint32_t keys;
    uint32_t comment_base;
    uint32_t comments;
} r6_root_ini_file_t;

typedef struct r6_root_ini_key_t {
    uint32_t key_offset;
    uint32_t key_length;
    uint32_t value_offset;
    uint32_t value_length;
} r6_root_ini_key_t;

R6_API int r6_root_ini_parse(const void *data, size_t size,
                             r6_root_ini_header_t *out);

R6_API int r6_root_ini_file(const void *data, size_t size, uint32_t index,
                            r6_root_ini_file_t *out);

R6_API int r6_root_ini_path(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_root_ini_section(const void *data, size_t size, uint32_t index,
                               char *out, size_t capacity);

R6_API int r6_root_ini_key(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity);

R6_API int r6_root_ini_value(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_root_ini_comment(const void *data, size_t size, uint32_t index,
                               char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
