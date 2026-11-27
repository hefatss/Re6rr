/* Freestanding reader for the complete shipped drive_story_* MessageID
 * namespace. The blob comes from tools/engine/story_key_namespace_catalog.py.
 * Source flags record only observed executable references; no scene, dialogue
 * or unlock mapping is inferred. */
#ifndef R6_STORY_KEY_NAMESPACE_H
#define R6_STORY_KEY_NAMESPACE_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_STORY_KEY_NAMESPACE_HEADER_SIZE 36
#define R6_STORY_KEY_NAMESPACE_RECORD_SIZE 20

enum r6_story_key_namespace_source {
    R6_STORY_KEY_NAMESPACE_MSGDB_ONLY = 0,
    R6_STORY_KEY_NAMESPACE_DIRECT = 1,
    R6_STORY_KEY_NAMESPACE_TABLE = 2
};

#define R6_STORY_KEY_NAMESPACE_NO_TABLE 0xFFFFFFFFu

typedef struct r6_story_key_namespace_header_t {
    uint32_t version;
    uint32_t count;
    uint32_t native_count;
    uint32_t string_size;
    uint32_t header_size;
    uint32_t strings_offset;
    uint32_t reserved;
} r6_story_key_namespace_header_t;

R6_API int r6_story_key_namespace_parse(
        const void *data, size_t size, r6_story_key_namespace_header_t *out);

/* Copied NUL-terminated ASCII key. */
R6_API int r6_story_key_namespace_name(const void *data, size_t size,
                                       uint32_t index, char *out,
                                       size_t capacity);

/* First exact-match row, or -1 when absent. */
R6_API int r6_story_key_namespace_find(const void *data, size_t size,
                                       const char *name);

/* Source flag and table index; non-table rows carry the NO_TABLE sentinel. */
R6_API int r6_story_key_namespace_fact(const void *data, size_t size,
                                       uint32_t index, uint32_t *source,
                                       uint32_t *table_index);

#ifdef __cplusplus
}
#endif

#endif
