/* Freestanding reader for validated 0x100 headers of shipped .MED motion
 * files. The blob comes from tools/engine/med_headers_catalog.py. Only the
 * copied header words and path are exposed; frame data is not interpreted. */
#ifndef R6_MED_HEADERS_H
#define R6_MED_HEADERS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_med_header {
    uint32_t version;
    uint32_t count;
    uint32_t header_off;
    uint32_t strings_size;
} r6_med_header;

typedef struct r6_med_row_t {
    uint32_t file_size;
    uint32_t frames;
    uint32_t word0;
    uint32_t word2;
    uint32_t word3;
    uint32_t word4;
    uint32_t word5;
    uint32_t word6;
    uint32_t word7;
} r6_med_row_t;

R6_API int r6_med_parse(const void *data, size_t size, r6_med_header *out);

/* Validates all eight raw header words and the derived byte counts. */
R6_API int r6_med_row(const void *data, size_t size, uint32_t index,
                      r6_med_row_t *out);

/* Copied NUL-terminated relative path from the dump. */
R6_API int r6_med_path(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
