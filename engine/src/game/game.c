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
        config->laps < 0 || config->rival_count < 0) {
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

int r6_game_write_config(const r6_game *game, void *buffer, size_t size) {
    unsigned char *bytes = (unsigned char *)buffer;
    uint32_t value;
    if (!game || !buffer || size < R6_ENMA_CFG_SIZE) {
        return R6_ERR_BUFFER;
    }
    write_u32(bytes, R6_ENMA_CFG_MODE, (uint32_t)game->config.mode);
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
    game->config.mode = (int)read_u32(bytes, R6_ENMA_CFG_MODE);
    game->config.stage = (int)read_u32(bytes, R6_ENMA_CFG_STAGE);
    game->config.area = (int)read_u32(bytes, R6_ENMA_CFG_AREA);
    value = read_u32(bytes, R6_ENMA_CFG_START_AZ);
    r6_memcpy(&game->config.start_az, &value, sizeof(value));
    value = read_u32(bytes, R6_ENMA_CFG_GOAL_ODO);
    r6_memcpy(&game->config.goal_odo, &value, sizeof(value));
    return R6_OK;
}
