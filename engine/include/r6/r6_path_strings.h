/* Freestanding reader for shipped executable and source path strings.
 * The derived blob comes from tools/engine/path_strings_catalog.py. */
#ifndef R6_PATH_STRINGS_H
#define R6_PATH_STRINGS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_PATH_STRINGS_GROUPS = 2,
    R6_PATH_STRINGS_EXE = 0,
    R6_PATH_STRINGS_SOURCE = 1,
    R6_PATH_STRINGS_COUNT = 1693,
    R6_PATH_STRINGS_NAME_CAP = 256
};

typedef struct r6_path_strings_header {
    uint32_t version;
    uint32_t group_count;
    uint32_t string_count;
    uint32_t strings_size;
} r6_path_strings_header;

R6_API int r6_path_strings_parse(const void *data, size_t size,
                                 r6_path_strings_header *out);

R6_API int r6_path_strings_group(const void *data, size_t size,
                                 uint32_t index, uint32_t *kind,
                                 uint32_t *count, uint32_t *first);

R6_API int r6_path_strings_get(const void *data, size_t size, uint32_t index,
                               char *out, size_t capacity);

R6_API int r6_path_strings_group_get(const void *data, size_t size,
                                     uint32_t group_index,
                                     uint32_t local_index, char *out,
                                     size_t capacity);

/* First exact match; R6_ERR_NOT_FOUND means no string matched. */
R6_API int r6_path_strings_find(const void *data, size_t size,
                                const char *text, uint32_t *group_index,
                                uint32_t *local_index,
                                uint32_t *global_index);

#ifdef __cplusplus
}
#endif

#endif
