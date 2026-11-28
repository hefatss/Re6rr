/* Freestanding inventory of shipped NTP config lines.
 * The blob comes from tools/engine/ntp_config_catalog.py. Paths, sizes, line
 * counts and verbatim ASCII lines with blank/comment/active kinds are copied.
 * Time-service behavior is not decoded. */
#ifndef R6_NTP_CONFIG_CATALOG_H
#define R6_NTP_CONFIG_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_ntp_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_ntp_header_t;

typedef struct r6_ntp_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t line_base;
} r6_ntp_file_t;

typedef struct r6_ntp_line_t {
    uint32_t text_offset;
    uint32_t text_length;
    uint32_t kind;
} r6_ntp_line_t;

R6_API int r6_ntp_parse(const void *data, size_t size, r6_ntp_header_t *out);

R6_API int r6_ntp_file(const void *data, size_t size, uint32_t index,
                       r6_ntp_file_t *out);

R6_API int r6_ntp_path(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

R6_API int r6_ntp_line(const void *data, size_t size, uint32_t index,
                       r6_ntp_line_t *out);

R6_API int r6_ntp_text(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
