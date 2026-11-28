/* Freestanding inventory of shipped keyconfig.toml lines.
 * The blob comes from tools/engine/keyconfig_toml_catalog.py. Path and
 * verbatim ASCII lines with blank/comment/active kinds are copied. Key
 * binding meaning and SDL token resolution stay unparsed. */
#ifndef R6_KEYCONFIG_TOML_CATALOG_H
#define R6_KEYCONFIG_TOML_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_keyconfig_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t active_count;
    uint32_t comment_count;
    uint32_t blank_count;
    uint32_t path_offset;
    uint32_t path_length;
} r6_keyconfig_header_t;

typedef struct r6_keyconfig_line_t {
    uint32_t text_offset;
    uint32_t text_length;
    uint32_t kind;
    uint32_t line;
} r6_keyconfig_line_t;

R6_API int r6_keyconfig_parse(const void *data, size_t size,
                              r6_keyconfig_header_t *out);

R6_API int r6_keyconfig_path(const void *data, size_t size, char *out,
                             size_t capacity);

R6_API int r6_keyconfig_line(const void *data, size_t size, uint32_t index,
                             r6_keyconfig_line_t *out);

R6_API int r6_keyconfig_text(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
