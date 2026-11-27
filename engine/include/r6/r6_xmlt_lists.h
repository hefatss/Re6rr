/* Freestanding inventory of shipped XMLT list/seed/field structure. The blob
 * comes from tools/engine/xmlt_lists_catalog.py. Text values are not copied;
 * only paths, tag names, counts and structural references cross the bridge. */
#ifndef R6_XMLT_LISTS_H
#define R6_XMLT_LISTS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_xmlt_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t list_count;
    uint32_t seed_count;
    uint32_t field_count;
    uint32_t type_count;
    uint32_t tag_count;
    uint32_t string_size;
    uint32_t reserved;
} r6_xmlt_header_t;

typedef struct r6_xmlt_file_t {
    uint32_t list_first;
    uint32_t list_count;
} r6_xmlt_file_t;

typedef struct r6_xmlt_list_t {
    uint32_t type_index;
    uint32_t seed_first;
    uint32_t seed_count;
    uint32_t field_first;
    uint32_t field_count;
} r6_xmlt_list_t;

typedef struct r6_xmlt_seed_t {
    uint32_t list_index;
    uint32_t field_first;
    uint32_t field_count;
} r6_xmlt_seed_t;

typedef struct r6_xmlt_field_t {
    uint32_t seed_index;
    uint32_t tag_index;
} r6_xmlt_field_t;

R6_API int r6_xmlt_lists_parse(const void *data, size_t size,
                               r6_xmlt_header_t *out);

R6_API int r6_xmlt_file(const void *data, size_t size, uint32_t index,
                        r6_xmlt_file_t *out);

R6_API int r6_xmlt_path(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

R6_API int r6_xmlt_list(const void *data, size_t size, uint32_t index,
                        r6_xmlt_list_t *out);

R6_API int r6_xmlt_type(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

R6_API int r6_xmlt_seed(const void *data, size_t size, uint32_t index,
                        r6_xmlt_seed_t *out);

R6_API int r6_xmlt_field(const void *data, size_t size, uint32_t index,
                         r6_xmlt_field_t *out);

R6_API int r6_xmlt_tag(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
