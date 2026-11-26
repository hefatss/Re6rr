/* Freestanding reader for shipped Environment.Lua value statistics. The
 * derived blob comes from tools/engine/scene_env_catalog.py. */
#ifndef R6_SCENE_ENV_H
#define R6_SCENE_ENV_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_SCENE_ENV_DIRS = 122,
    R6_SCENE_ENV_ACTORS = 4,
    R6_SCENE_ENV_NAME_CAP = 0x80
};

typedef struct r6_scene_env_header {
    uint32_t dirs;
    uint32_t present;
    uint32_t actor_slots;
    uint32_t present_slots;
    uint32_t nonzero;
    uint32_t unique_actors;
    uint32_t actor_min;
    uint32_t actor_max;
    uint32_t stages;
    uint32_t unique_stages;
    uint32_t stage_min;
    uint32_t stage_max;
    uint32_t strings_size;
} r6_scene_env_header;

typedef struct r6_scene_env_row_t {
    uint32_t present;
    uint32_t stage;
    uint32_t stage_root;
    uint32_t stage_day;
    uint32_t cam_id;
    uint32_t actors[R6_SCENE_ENV_ACTORS];
} r6_scene_env_row_t;

R6_API int r6_scene_env_parse(const void *data, size_t size,
                              r6_scene_env_header *out);

R6_API int r6_scene_env_name(const void *data, size_t size, uint32_t index,
                             char *name, size_t capacity);

R6_API int r6_scene_env_row(const void *data, size_t size, uint32_t index,
                            r6_scene_env_row_t *out);

R6_API int r6_scene_env_find(const void *data, size_t size,
                             const char *name, uint32_t *index);

#ifdef __cplusplus
}
#endif

#endif
