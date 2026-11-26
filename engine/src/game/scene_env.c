/* Bounded reader for the derived scene environment inventory. No file access,
 * Lua execution or allocation happens in the core. */

#include "r6/r6_scene_env.h"

#include "core/internal.h"

static const unsigned char scene_env_magic[8] = {
    'R', '6', 'S', 'E', 'S', 0, 1, 0
};

static int scene_env_header(const void *data, size_t size,
                            r6_scene_env_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t rows_end = 64u + R6_SCENE_ENV_DIRS * 40u;
    if (!bytes || !out || size <= rows_end ||
        r6_memcmp(bytes, scene_env_magic, sizeof(scene_env_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_SCENE_ENV_DIRS ||
        r6_u32(bytes, 20) != R6_SCENE_ENV_DIRS * R6_SCENE_ENV_ACTORS) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->dirs = r6_u32(bytes, 12);
    out->present = r6_u32(bytes, 16);
    out->actor_slots = r6_u32(bytes, 20);
    out->present_slots = r6_u32(bytes, 24);
    out->nonzero = r6_u32(bytes, 28);
    out->unique_actors = r6_u32(bytes, 32);
    out->actor_min = r6_u32(bytes, 36);
    out->actor_max = r6_u32(bytes, 40);
    out->stages = r6_u32(bytes, 44);
    out->unique_stages = r6_u32(bytes, 48);
    out->stage_min = r6_u32(bytes, 52);
    out->stage_max = r6_u32(bytes, 56);
    out->strings_size = r6_u32(bytes, 60);
    if (!out->strings_size ||
        (uint64_t)rows_end + out->strings_size != size ||
        out->present > out->dirs || out->present_slots !=
        out->present * R6_SCENE_ENV_ACTORS ||
        out->nonzero > out->present_slots ||
        out->actor_min > out->actor_max ||
        out->stage_min > out->stage_max) {
        r6_memset(out, 0, sizeof(*out));
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int scene_env_name_at(const unsigned char *bytes, size_t size,
                             uint32_t offset, char *name, size_t capacity) {
    uint32_t rows_end = 64u + R6_SCENE_ENV_DIRS * 40u;
    uint32_t at = offset;
    if (offset < rows_end || offset >= size) {
        return R6_ERR_FORMAT;
    }
    while (at < size && bytes[at]) {
        at++;
    }
    if (at == size || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(name, bytes + offset, at - offset);
    name[at - offset] = 0;
    return R6_OK;
}

static int scene_env_row_at(const void *data, size_t size, uint32_t index,
                            const unsigned char **bytes,
                            uint32_t *row_off) {
    r6_scene_env_header header;
    int result = scene_env_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.dirs) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = 64u + index * 40u;
    return R6_OK;
}

int r6_scene_env_parse(const void *data, size_t size,
                       r6_scene_env_header *out) {
    return scene_env_header(data, size, out);
}

int r6_scene_env_name(const void *data, size_t size, uint32_t index,
                      char *name, size_t capacity) {
    const unsigned char *bytes;
    uint32_t row_off;
    int result = scene_env_row_at(data, size, index, &bytes, &row_off);
    if (result != R6_OK || !name || !capacity) {
        return result == R6_OK ? R6_ERR_ARG : result;
    }
    return scene_env_name_at(bytes, size, r6_u32(bytes, row_off), name,
                             capacity);
}

int r6_scene_env_row(const void *data, size_t size, uint32_t index,
                     r6_scene_env_row_t *out) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t at;
    int result = scene_env_row_at(data, size, index, &bytes, &row_off);
    if (result != R6_OK || !out) {
        return result == R6_OK ? R6_ERR_ARG : result;
    }
    if (r6_u32(bytes, row_off + 4u) > 1u ||
        r6_u32(bytes, row_off) < 64u + R6_SCENE_ENV_DIRS * 40u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->present = r6_u32(bytes, row_off + 4u);
    out->stage = r6_u32(bytes, row_off + 8u);
    out->stage_root = r6_u32(bytes, row_off + 12u);
    out->stage_day = r6_u32(bytes, row_off + 16u);
    out->cam_id = r6_u32(bytes, row_off + 20u);
    for (at = 0; at < R6_SCENE_ENV_ACTORS; at++) {
        out->actors[at] = r6_u32(bytes, row_off + 24u + at * 4u);
    }
    return R6_OK;
}

int r6_scene_env_find(const void *data, size_t size,
                      const char *name, uint32_t *index) {
    r6_scene_env_header header;
    const unsigned char *bytes;
    uint32_t length;
    uint32_t at;
    char candidate[R6_SCENE_ENV_NAME_CAP];
    int result = scene_env_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!name || !index) {
        return R6_ERR_ARG;
    }
    length = (uint32_t)r6_strlen(name);
    if (!length || length >= sizeof(candidate)) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    for (at = 0; at < header.dirs; at++) {
        uint32_t row_off = 64u + at * 40u;
        if (scene_env_name_at(bytes, size, r6_u32(bytes, row_off), candidate,
                              sizeof(candidate)) != R6_OK) {
            return R6_ERR_FORMAT;
        }
        if (r6_memcmp(candidate, name, length) == 0 &&
            candidate[length] == 0) {
            *index = at;
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}
