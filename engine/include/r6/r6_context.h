/* Ordered per-car Lua script path templates from the shipped loader. No files
 * are read here; the host checks existence and supplies the script bytes. */
#ifndef R6_CONTEXT_H
#define R6_CONTEXT_H

#include <stddef.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_CONTEXT_TIRE = 0,
    R6_CONTEXT_POSITION = 1,
    R6_CONTEXT_SHADER = 2,
    R6_CONTEXT_SPECIFICATION = 3,
    R6_CONTEXT_COLOR = 4,
    R6_CONTEXT_SETS = 5,
    R6_CONTEXT_PATH_COUNT = 12,
    R6_CONTEXT_PATH_CAP = 0x100
};

/* Write one slash-separated relative path into out. set is one of the five
 * load groups, index is local to that group; car/model may contain only
 * letters, digits and underscore. Returns R6_ERR_NOT_FOUND for an unused
 * index and R6_ERR_BUFFER if capacity is too small. */
R6_API int r6_context_path(int set, int index, const char *car,
                           const char *model, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
