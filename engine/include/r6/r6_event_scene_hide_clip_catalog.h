/* Freestanding inventory of shipped event-scene hide-clip model names. The
 * blob comes from tools/engine/event_scene_hide_clip_catalog.py. Names and the
 * accessor name are copied; no scene timing or visibility is inferred. */
#ifndef R6_EVENT_SCENE_HIDE_CLIP_CATALOG_H
#define R6_EVENT_SCENE_HIDE_CLIP_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_event_scene_hide_clip_header_t {
    uint32_t version;
    uint32_t name_count;
    uint32_t string_size;
    uint32_t table_size;
    uint32_t accessor_size;
} r6_event_scene_hide_clip_header_t;

R6_API int r6_event_scene_hide_clip_parse(
    const void *data, size_t size, r6_event_scene_hide_clip_header_t *out);

R6_API int r6_event_scene_hide_clip_name(const void *data, size_t size,
                                         uint32_t index, char *out,
                                         size_t capacity);

R6_API int r6_event_scene_hide_clip_accessor(const void *data, size_t size,
                                             char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
