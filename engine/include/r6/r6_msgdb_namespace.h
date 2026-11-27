/* Freestanding inventory of every shipped MessageID in msgdb.lua. The blob
 * comes from tools/engine/msgdb_namespace_catalog.py. Only copied names,
 * byte offsets and four-character groups cross the bridge. */
#ifndef R6_MSGDB_NAMESPACE_H
#define R6_MSGDB_NAMESPACE_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_MSGDB_GROUP_LENGTH 4

typedef struct r6_msgdb_header_t {
    uint32_t version;
    uint32_t count;
    uint32_t group_count;
    uint32_t string_size;
    uint32_t msgdb_size;
    uint32_t story_count;
} r6_msgdb_header_t;

R6_API int r6_msgdb_namespace_parse(const void *data, size_t size,
                                    r6_msgdb_header_t *out);

/* Copied ASCII MessageID. */
R6_API int r6_msgdb_namespace_key(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity);

/* First exact-match row, or -1 when absent. */
R6_API int r6_msgdb_namespace_find(const void *data, size_t size,
                                   const char *key);

/* Source byte offset in msgdb.lua and the four-character group index. */
R6_API int r6_msgdb_namespace_fact(const void *data, size_t size,
                                   uint32_t index, uint32_t *byte_offset,
                                   uint32_t *group_index);

/* Copied four-character group name. */
R6_API int r6_msgdb_namespace_group(const void *data, size_t size,
                                    uint32_t index, char *out,
                                    size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
