/* Deterministic game-flow state machine. No CRT, no files, no host calls. */

#include "r6/r6_game.h"

#include "core/internal.h"

struct r6_game {
    r6_game_config config;
    int phase;
    int result;
    float result_time;
};

size_t r6_game_size(void) {
    return sizeof(r6_game);
}

void r6_game_config_default(r6_game_config *config) {
    if (!config) {
        return;
    }
    r6_memset(config, 0, sizeof(*config));
    config->mode = R6_ENMA_MODE_BATTLE;
    config->stage = 3;              /* SConfigPlay default in the dump */
    config->area = 1;               /* HAKONE */
    config->course = R6_ENMA_COURSE_HAKONE;
    config->car_index = 0;
    config->rival_count = 0;
    config->goal_odo = 100000000.0f;
    config->time_limit = 0.0f;
    config->countdown = 3.0f;
    config->laps = 1;
    config->series = 0;
    config->character_count = 0;
    config->battle_ramp = 0;
    config->battle_run_dist = 0.0f;
    config->target_stage = 0;
    config->target_tutorial = 0;
    config->sampling = 0;
    config->random_seed = 0;
    config->operation_jct = 0;
}

r6_game *r6_game_init(void *storage, size_t size,
                      const r6_game_config *config) {
    r6_game *game;
    if (!storage || size < sizeof(r6_game)) {
        return 0;
    }
    game = (r6_game *)storage;
    r6_memset(game, 0, sizeof(*game));
    if (config) {
        game->config = *config;
    } else {
        r6_game_config_default(&game->config);
    }
    game->phase = R6_GAME_SELECT_CAR;
    return game;
}

int r6_game_get_config(const r6_game *game, r6_game_config *out) {
    if (!game || !out) {
        return R6_ERR_ARG;
    }
    *out = game->config;
    return R6_OK;
}

int r6_game_set_config(r6_game *game, const r6_game_config *config) {
    if (!game || !config || config->mode < 0 || config->mode > 8 ||
        config->laps < 0 || config->rival_count < 0 ||
        config->series < 0 || config->character_count < 0 ||
        config->battle_ramp < 0 || config->target_stage < 0 ||
        config->target_tutorial < 0 || config->target_tutorial > 1 ||
        config->sampling < 0 || config->sampling > 1) {
        return R6_ERR_ARG;
    }
    game->config = *config;
    return R6_OK;
}

int r6_game_phase(const r6_game *game) {
    return game ? game->phase : -1;
}

int r6_game_select_car(r6_game *game, int index) {
    if (!game) {
        return R6_ERR_ARG;
    }
    if (game->phase != R6_GAME_SELECT_CAR) {
        return R6_ERR_STATE;
    }
    if (index < 0) {
        return R6_ERR_ARG;
    }
    game->config.car_index = index;
    return R6_OK;
}

int r6_game_select_course(r6_game *game, int course, int area, int stage) {
    if (!game || game->phase != R6_GAME_SELECT_CAR || course < 0 ||
        area < 0 || stage < 0) {
        return R6_ERR_STATE;
    }
    game->config.course = course;
    game->config.area = area;
    game->config.stage = stage;
    game->phase = R6_GAME_SELECT_COURSE;
    return R6_OK;
}

int r6_game_start(r6_game *game) {
    if (!game || game->phase != R6_GAME_SELECT_COURSE) {
        return R6_ERR_STATE;
    }
    game->result = R6_RACE_NONE;
    game->result_time = 0.0f;
    game->phase = R6_GAME_RACE;
    return R6_OK;
}

int r6_game_step(r6_game *game, float dt, const r6_race_state *race_state) {
    if (!game || dt < 0.0f || dt != dt) {
        return R6_ERR_ARG;
    }
    if (game->phase != R6_GAME_RACE) {
        return R6_OK;
    }
    if (!race_state) {
        return R6_ERR_ARG;
    }
    game->result_time += dt;
    if (race_state->outcome == R6_RACE_GOAL ||
        race_state->outcome == R6_RACE_TIME_UP ||
        race_state->outcome == R6_RACE_RETIRE ||
        race_state->outcome == R6_RACE_WRONG_WAY) {
        game->result = race_state->outcome;
        game->result_time = race_state->elapsed;
        game->phase = R6_GAME_RESULT;
    }
    return R6_OK;
}

int r6_game_reset(r6_game *game) {
    if (!game) {
        return R6_ERR_ARG;
    }
    game->result = R6_RACE_NONE;
    game->result_time = 0.0f;
    game->phase = R6_GAME_SELECT_CAR;
    return R6_OK;
}

static void write_u32(unsigned char *bytes, size_t at, uint32_t value) {
    bytes[at] = (unsigned char)value;
    bytes[at + 1] = (unsigned char)(value >> 8);
    bytes[at + 2] = (unsigned char)(value >> 16);
    bytes[at + 3] = (unsigned char)(value >> 24);
}

static uint32_t read_u32(const unsigned char *bytes, size_t at) {
    return (uint32_t)bytes[at] |
           ((uint32_t)bytes[at + 1] << 8) |
           ((uint32_t)bytes[at + 2] << 16) |
           ((uint32_t)bytes[at + 3] << 24);
}

static void write_u8(unsigned char *bytes, size_t at, uint32_t value) {
    bytes[at] = (unsigned char)value;
}

static uint32_t read_u8(const unsigned char *bytes, size_t at) {
    return bytes[at];
}

int r6_game_write_config(const r6_game *game, void *buffer, size_t size) {
    unsigned char *bytes = (unsigned char *)buffer;
    uint32_t value;
    if (!game || !buffer || size < R6_ENMA_CFG_SIZE) {
        return R6_ERR_BUFFER;
    }
    write_u32(bytes, R6_ENMA_CFG_OPERATION_JCT,
              (uint32_t)game->config.operation_jct);
    write_u32(bytes, R6_ENMA_CFG_RANDOM_SEED,
              (uint32_t)game->config.random_seed);
    write_u32(bytes, R6_ENMA_CFG_MODE, (uint32_t)game->config.mode);
    write_u32(bytes, R6_ENMA_CFG_STORY_SERIES,
              (uint32_t)game->config.series);
    write_u32(bytes, R6_ENMA_CFG_STORY_LAPS, (uint32_t)game->config.laps);
    write_u32(bytes, R6_ENMA_CFG_STORY_CHARS,
              (uint32_t)game->config.character_count);
    write_u32(bytes, R6_ENMA_CFG_BATTLE_RAMP,
              (uint32_t)game->config.battle_ramp);
    r6_memcpy(&value, &game->config.battle_run_dist, sizeof(value));
    write_u32(bytes, R6_ENMA_CFG_BATTLE_RUN_DIST, value);
    write_u32(bytes, R6_ENMA_CFG_BATTLE_RIVALS,
              (uint32_t)game->config.rival_count);
    write_u32(bytes, R6_ENMA_CFG_TARGET_STAGE,
              (uint32_t)game->config.target_stage);
    write_u8(bytes, R6_ENMA_CFG_TARGET_TUTORIAL,
             (uint32_t)game->config.target_tutorial);
    write_u8(bytes, R6_ENMA_CFG_SAMPLING, (uint32_t)game->config.sampling);
    write_u32(bytes, R6_ENMA_CFG_STAGE, (uint32_t)game->config.stage);
    write_u32(bytes, R6_ENMA_CFG_AREA, (uint32_t)game->config.area);
    r6_memcpy(&value, &game->config.start_az, sizeof(value));
    write_u32(bytes, R6_ENMA_CFG_START_AZ, value);
    r6_memcpy(&value, &game->config.goal_odo, sizeof(value));
    write_u32(bytes, R6_ENMA_CFG_GOAL_ODO, value);
    return R6_OK;
}

int r6_game_read_config(r6_game *game, const void *buffer, size_t size) {
    const unsigned char *bytes = (const unsigned char *)buffer;
    uint32_t value;
    if (!game || !buffer || size < R6_ENMA_CFG_SIZE) {
        return R6_ERR_BUFFER;
    }
    game->config.operation_jct =
        (int)read_u32(bytes, R6_ENMA_CFG_OPERATION_JCT);
    game->config.random_seed = (int)read_u32(bytes, R6_ENMA_CFG_RANDOM_SEED);
    game->config.mode = (int)read_u32(bytes, R6_ENMA_CFG_MODE);
    game->config.series = (int)read_u32(bytes, R6_ENMA_CFG_STORY_SERIES);
    game->config.laps = (int)read_u32(bytes, R6_ENMA_CFG_STORY_LAPS);
    game->config.character_count =
        (int)read_u32(bytes, R6_ENMA_CFG_STORY_CHARS);
    game->config.battle_ramp =
        (int)read_u32(bytes, R6_ENMA_CFG_BATTLE_RAMP);
    value = read_u32(bytes, R6_ENMA_CFG_BATTLE_RUN_DIST);
    r6_memcpy(&game->config.battle_run_dist, &value, sizeof(value));
    game->config.rival_count =
        (int)read_u32(bytes, R6_ENMA_CFG_BATTLE_RIVALS);
    game->config.target_stage =
        (int)read_u32(bytes, R6_ENMA_CFG_TARGET_STAGE);
    game->config.target_tutorial =
        (int)read_u8(bytes, R6_ENMA_CFG_TARGET_TUTORIAL);
    game->config.sampling = (int)read_u8(bytes, R6_ENMA_CFG_SAMPLING);
    game->config.stage = (int)read_u32(bytes, R6_ENMA_CFG_STAGE);
    game->config.area = (int)read_u32(bytes, R6_ENMA_CFG_AREA);
    value = read_u32(bytes, R6_ENMA_CFG_START_AZ);
    r6_memcpy(&game->config.start_az, &value, sizeof(value));
    value = read_u32(bytes, R6_ENMA_CFG_GOAL_ODO);
    r6_memcpy(&game->config.goal_odo, &value, sizeof(value));
    return R6_OK;
}

static void scene_put_i32(unsigned char *bytes, size_t offset, int32_t value) {
    uint32_t bits = (uint32_t)value;
    bytes[offset] = (unsigned char)bits;
    bytes[offset + 1] = (unsigned char)(bits >> 8);
    bytes[offset + 2] = (unsigned char)(bits >> 16);
    bytes[offset + 3] = (unsigned char)(bits >> 24);
}

int r6_scene_write_camid(const void *scene, size_t scene_size, void *config,
                         size_t config_size, int32_t *out) {
    const unsigned char *source = (const unsigned char *)scene;
    unsigned char *target = (unsigned char *)config;
    int32_t camid;
    if (!source || !target || !out ||
        scene_size < R6_SCENE_SIZE ||
        config_size < R6_SCENE_CONFIG_CAMID_OFFSET + 4u) {
        return R6_ERR_ARG;
    }
    camid = (int32_t)read_u32(source, R6_SCENE_CAMID_OFFSET);
    scene_put_i32(target, R6_SCENE_CONFIG_CAMID_OFFSET, camid);
    *out = camid;
    return R6_OK;
}

int r6_scene_container_offset(uint32_t slot, size_t *out) {
    if (!out || slot >= R6_SCENE_CONTAINER_COUNT) {
        return R6_ERR_ARG;
    }
    *out = R6_SCENE_CONTAINER_BASE + (size_t)slot * R6_SCENE_CONTAINER_STRIDE;
    return R6_OK;
}

int r6_scene_runtime_camera(const void *records, size_t size, int32_t frame) {
    const unsigned char *bytes = (const unsigned char *)records;
    size_t count;
    size_t index;
    if (!bytes) {
        return -1;
    }
    count = size / R6_SCENE_RECORD_SIZE;
    for (index = 0; index < count; index++) {
        size_t at = index * R6_SCENE_RECORD_SIZE;
        int32_t type = (int32_t)read_u32(bytes, at);
        int32_t start = (int32_t)read_u32(bytes, at + 4u);
        int32_t end = (int32_t)read_u32(bytes, at + 8u);
        int32_t exact = (int32_t)read_u32(bytes, at + 12u);
        if (type == -1 || end < 0) {
            continue;
        }
        if (exact == 1 ? start == frame : start <= frame && frame <= end) {
            return (int)index;
        }
    }
    return -1;
}

static float ees_f32(const unsigned char *bytes, size_t at) {
    float value;
    r6_memcpy(&value, bytes + at, sizeof(value));
    return value;
}

int r6_ees_camera_fields(const void *data, size_t size, uint32_t offset,
                         r6_ees_camera_fields_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = offset;
    if (!bytes || !out || base > size ||
        size - base < R6_EES_CAMERA_STRIDE) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    out->m_CamType = (int32_t)read_u32(bytes, base + 0x00);
    out->m_StratFrame = (int32_t)read_u32(bytes, base + 0x04);
    out->m_ActFrame = ees_f32(bytes, base + 0x08);
    out->m_WiatMode = (uint8_t)read_u8(bytes, base + 0x0C);
    out->m_StratFieldAngle = ees_f32(bytes, base + 0x90);
    out->m_EndFieldAngle = ees_f32(bytes, base + 0x94);
    out->m_FieldAngleCalcId = (int32_t)read_u32(bytes, base + 0x98);
    out->m_GlobalLookAt = (int32_t)read_u32(bytes, base + 0xA8);
    out->m_LookAtId = (int32_t)read_u32(bytes, base + 0xB4);
    out->m_LookAtStartRenge = ees_f32(bytes, base + 0xB8);
    out->m_LookAtStartCamRotX = ees_f32(bytes, base + 0xBC);
    out->m_LookAtStartCamRotY = ees_f32(bytes, base + 0xC0);
    out->m_LookAtStartCamRotZ = ees_f32(bytes, base + 0xC4);
    out->m_LookAtEndRenge = ees_f32(bytes, base + 0xC8);
    out->m_LookAtEndCamRotX = ees_f32(bytes, base + 0xCC);
    out->m_LookAtEndCamRotY = ees_f32(bytes, base + 0xD0);
    out->m_LookAtEndCamRotZ = ees_f32(bytes, base + 0xD4);
    out->m_TransCalcId = (int32_t)read_u32(bytes, base + 0xD8);
    out->m_RotCalcId = (int32_t)read_u32(bytes, base + 0xDC);
    out->m_StratOpRotZ = ees_f32(bytes, base + 0xE0);
    out->m_EndOpRotZ = ees_f32(bytes, base + 0xE4);
    out->m_OpRotZCalcId = (int32_t)read_u32(bytes, base + 0xE8);
    out->m_LookAtStartOfsetPosX = ees_f32(bytes, base + 0xEC);
    out->m_LookAtStartOfsetPosY = ees_f32(bytes, base + 0xF0);
    out->m_LookAtStartOfsetPosZ = ees_f32(bytes, base + 0xF4);
    out->m_LookAtEndOfsetPosX = ees_f32(bytes, base + 0xF8);
    out->m_LookAtEndOfsetPosY = ees_f32(bytes, base + 0xFC);
    out->m_LookAtEndOfsetPosZ = ees_f32(bytes, base + 0x100);
    out->m_OfsetCalcId = (int32_t)read_u32(bytes, base + 0x104);
    out->m_StartConnection = (int32_t)read_u32(bytes, base + 0x108);
    out->m_EndConnection = (int32_t)read_u32(bytes, base + 0x10C);
    return R6_OK;
}

int r6_scene_pack(const r6_scene_values_t *values, void *out, size_t size) {
    unsigned char *bytes = (unsigned char *)out;
    uint32_t index;
    if (!values || !bytes || size < R6_SCENE_SIZE) {
        return R6_ERR_ARG;
    }
    r6_memset(bytes, 0, R6_SCENE_SIZE);
    write_u32(bytes, 0x08, (uint32_t)values->stage);
    write_u32(bytes, 0x0C, (uint32_t)values->stage_root);
    write_u32(bytes, 0x10, (uint32_t)values->stage_day);
    write_u32(bytes, R6_SCENE_CAMID_OFFSET, (uint32_t)values->cam_id);
    for (index = 0; index < 4u; index++) {
        write_u32(bytes, 0x14u + index * 4u,
                  (uint32_t)values->actors[index]);
    }
    return R6_OK;
}

static const unsigned char scene_names_magic[8] = {
    'R', '6', 'S', 'C', 'N', 0, 1, 0
};

int r6_scene_names_parse(const void *data, size_t size,
                         r6_scene_names_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t total = 0;
    uint32_t strings_off;
    uint32_t index;
    if (!bytes || !out || size < 40u ||
        r6_memcmp(bytes, scene_names_magic, sizeof(scene_names_magic)) != 0 ||
        read_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    for (index = 0; index < R6_SCENE_NAMES_KINDS; index++) {
        out->counts[index] = read_u32(bytes, 12u + index * 4u);
        total += out->counts[index];
    }
    strings_off = 40u + total * 4u;
    if (strings_off >= size) {
        return R6_ERR_FORMAT;
    }
    for (index = 0; index < R6_SCENE_NAMES_KINDS; index++) {
        if (read_u32(bytes, 24u + index * 4u) != strings_off) {
            return R6_ERR_FORMAT;
        }
    }
    out->strings_off = strings_off;
    out->strings_size = read_u32(bytes, 36u);
    if (out->strings_size < 1u ||
        (uint64_t)strings_off + out->strings_size != size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int scene_copy_name(const unsigned char *bytes, size_t size,
                           uint32_t offset, char *out, size_t capacity) {
    size_t length = 0;
    if (!capacity || offset >= size) {
        return R6_ERR_ARG;
    }
    while (offset + length < size && bytes[offset + length]) {
        length++;
    }
    if (!length) {
        return R6_ERR_NOT_FOUND;
    }
    if (length >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memset(out, 0, capacity);
    r6_memcpy(out, bytes + offset, length);
    return R6_OK;
}

int r6_scene_names_get(const void *data, size_t size, int kind,
                       int32_t value, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_scene_names_header header;
    uint32_t index;
    uint32_t offset;
    int result;
    if (r6_scene_names_parse(data, size, &header) != R6_OK || !out ||
        kind < R6_SCENE_CAR_NAMES || kind > R6_SCENE_DAY_NAMES) {
        return R6_ERR_ARG;
    }
    if (kind == R6_SCENE_CAR_NAMES) {
        if (value == -1 || value < 0 ||
            (uint32_t)value >= header.counts[R6_SCENE_CAR_NAMES]) {
            if (capacity < 9u) {
                return R6_ERR_BUFFER;
            }
            r6_memcpy(out, "PLC_NON", 8u);
            return R6_OK;
        }
        index = (uint32_t)value;
    } else if (kind == R6_SCENE_STAGE_NAMES) {
        if (value <= 0 || (uint32_t)(value - 1) >=
            header.counts[R6_SCENE_STAGE_NAMES]) {
            return R6_ERR_NOT_FOUND;
        }
        index = (uint32_t)(value - 1);
    } else {
        if (value < 0 || (uint32_t)value >= header.counts[R6_SCENE_DAY_NAMES]) {
            return R6_ERR_NOT_FOUND;
        }
        index = (uint32_t)value;
    }
    offset = read_u32(bytes, 40u + index * 4u);
    if (kind == R6_SCENE_CAR_NAMES) {
        /* later table arrays follow the car offsets */
    } else if (kind == R6_SCENE_STAGE_NAMES) {
        offset = read_u32(bytes, 40u + header.counts[R6_SCENE_CAR_NAMES] * 4u +
                                index * 4u);
    } else {
        offset = read_u32(bytes, 40u +
                          (header.counts[R6_SCENE_CAR_NAMES] +
                           header.counts[R6_SCENE_STAGE_NAMES]) * 4u +
                          index * 4u);
    }
    if (offset < header.strings_off || offset >= size) {
        return R6_ERR_FORMAT;
    }
    result = scene_copy_name(bytes, size, offset, out, capacity);
    return result == R6_ERR_ARG ? R6_ERR_FORMAT : result;
}
