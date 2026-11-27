/* Freestanding inventory of shipped Enma ytErrorLogMerge layout facts. The
 * blob comes from tools/engine/enma_error_log_catalog.py. Paths, sizes, line
 * counts and distinct token counts are copied; numeric log values are not. */
#ifndef R6_ENMA_ERROR_LOG_CATALOG_H
#define R6_ENMA_ERROR_LOG_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_enma_error_log_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t total_bytes;
    uint32_t total_lines;
    uint32_t crlf_count;
    uint32_t sector_lines;
    uint32_t vector_lines;
    uint32_t sector_files;
} r6_enma_error_log_header_t;

typedef struct r6_enma_error_log_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t shape;
    uint32_t line_min;
    uint32_t line_max;
    uint32_t crlf;
    uint32_t tokens;
} r6_enma_error_log_file_t;

R6_API int r6_enma_error_log_parse(const void *data, size_t size,
                                   r6_enma_error_log_header_t *out);

R6_API int r6_enma_error_log_file(const void *data, size_t size, uint32_t index,
                                  r6_enma_error_log_file_t *out);

R6_API int r6_enma_error_log_path(const void *data, size_t size,
                                  uint32_t index, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
