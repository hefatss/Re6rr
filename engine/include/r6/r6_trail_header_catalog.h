/* Freestanding inventory of shipped Enma trail headers.
 * The blob comes from tools/engine/trail_header_catalog.py. File names, link
 * counts, ASCII link names, marker words, record counts and trailer words are
 * copied. The 52-byte records and their semantics stay unparsed. */
#ifndef R6_TRAIL_HEADER_CATALOG_H
#define R6_TRAIL_HEADER_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_th_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t name_count;
    uint32_t source_bytes;
    uint32_t record_count;
    uint32_t record_size;
    uint32_t string_size;
    uint32_t marker_word;
    uint32_t reserved;
} r6_th_header_t;

typedef struct r6_th_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t size;
    uint32_t links;
    uint32_t name_base;
    uint32_t name_count;
    uint32_t marker_offset;
    uint32_t marker_word;
    uint32_t record_count;
    uint32_t trailer;
} r6_th_file_t;

typedef struct r6_th_name_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t source_offset;
} r6_th_name_t;

R6_API int r6_th_parse(const void *data, size_t size, r6_th_header_t *out);

R6_API int r6_th_file(const void *data, size_t size, uint32_t index,
                      r6_th_file_t *out);

R6_API int r6_th_path(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity);

R6_API int r6_th_name(const void *data, size_t size, uint32_t index,
                      r6_th_name_t *out);

R6_API int r6_th_name_text(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
