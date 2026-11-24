/* Freestanding game flow and SConfigPlay bridge.
 *
 * Phase transitions model the minimum sequence required to go from car select
 * to a race result. Serialization writes only fields whose byte offsets were
 * recovered from the shipped Enma DLL; unknown fields are left untouched.
 */
#ifndef R6_GAME_H
#define R6_GAME_H

#include <stddef.h>
#include <stdint.h>

#include "r6/r6.h"
#include "r6/r6_enma.h"
#include "r6/r6_race.h"

#ifdef __cplusplus
extern "C" {
#endif

/* SetDefault poisons only the first 0x464 bytes, but SConfigPlay also holds
 * the RaceField/Phantom fields up to 0x640 read by FUN_1407a9c80. */
#define R6_ENMA_CFG_SETDEFAULT_SIZE 1124u
#define R6_ENMA_CFG_SIZE 1604u

enum r6_game_phase {
    R6_GAME_TITLE = 0,
    R6_GAME_SELECT_CAR = 1,
    R6_GAME_SELECT_COURSE = 2,
    R6_GAME_RACE = 3,
    R6_GAME_RESULT = 4
};

typedef struct r6_game_config {
    int mode;         /* r6_enma_game_mode */
    int stage;        /* EStage */
    int area;         /* EAreaId */
    int course;       /* r6_enma_course */
    int car_index;
    int rival_count;
    float start_az;
    float goal_odo;
    float time_limit;
    float countdown;
    int laps;
    int series;
    int character_count;
    int battle_ramp;
    float battle_run_dist;
    int target_stage;
    int target_tutorial;
    int sampling;
    int random_seed;
    int operation_jct;
} r6_game_config;

typedef struct r6_game r6_game;

R6_API size_t r6_game_size(void);
R6_API void r6_game_config_default(r6_game_config *config);
R6_API r6_game *r6_game_init(void *storage, size_t size,
                             const r6_game_config *config);
R6_API int r6_game_get_config(const r6_game *game, r6_game_config *out);
R6_API int r6_game_set_config(r6_game *game, const r6_game_config *config);
R6_API int r6_game_phase(const r6_game *game);
R6_API int r6_game_select_car(r6_game *game, int index);
R6_API int r6_game_select_course(r6_game *game, int course, int area,
                                 int stage);
R6_API int r6_game_start(r6_game *game);
R6_API int r6_game_step(r6_game *game, float dt,
                        const r6_race_state *race_state);
R6_API int r6_game_reset(r6_game *game);

/* Enma byte contract. Buffer must be at least R6_ENMA_CFG_SIZE bytes. */
R6_API int r6_game_write_config(const r6_game *game, void *buffer,
                                size_t size);
R6_API int r6_game_read_config(r6_game *game, const void *buffer, size_t size);

#ifdef __cplusplus
}
#endif

#endif
