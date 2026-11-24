/* Race rules around the freestanding vehicle and course modules.
 *
 * The state names follow the EPlayState enum exported by the shipped Enma DLL.
 * Rules are intentionally simple and deterministic: countdown, progress along
 * the course, lap/timing, wrong-way detection, course-flag checkpoints/goal and
 * optional follow-the-course rival AI.
 */
#ifndef R6_RACE_H
#define R6_RACE_H

#include <stddef.h>

#include "r6/r6.h"
#include "r6/r6_course.h"
#include "r6/r6_enma.h"
#include "r6/r6_physics.h"

#ifdef __cplusplus
extern "C" {
#endif

enum r6_race_outcome {
    R6_RACE_NONE = 0,
    R6_RACE_RUNNING = 1,
    R6_RACE_GOAL = 2,
    R6_RACE_TIME_UP = 3,
    R6_RACE_RETIRE = 4,
    R6_RACE_WRONG_WAY = 5,
    R6_RACE_COLLISION = 6
};

#define R6_RACE_MAX_RIVALS 8
#define R6_RACE_MAX_CHECKPOINTS 16

typedef struct r6_race_config {
    int mode;             /* EGameMode */
    int stage;            /* EStage */
    int course;           /* ECourse */
    int area;             /* EAreaId */
    float goal_odo;       /* 0 = disabled; from SConfigPlay.fGoalOdo */
    float time_limit;     /* 0 = unlimited */
    float countdown;      /* seconds */
    int laps;             /* 0 = disabled */
    float wrong_way_limit; /* seconds of sustained reverse travel */
    float offroad_factor;  /* lateral/half_width before off-road starts */
} r6_race_config;

/* Up to eight rivals can be placed by the host or spawned as simple AI cars.
 * `checkpoint_mask` is a visited ordinal mask, not raw vertex flags. */
typedef struct r6_rival_state {
    float x, y, z;
    float yaw;
    float speed;
    float s;
    float lateral;
    uint32_t id;
} r6_rival_state;

typedef struct r6_race_state {
    int play_state;       /* r6_enma_play_state */
    int outcome;          /* r6_race_outcome */
    float elapsed;
    float countdown;
    int lap;
    float lap_time;
    float last_lap;
    float best_lap;
    float s;              /* arc length on current lap */
    float progress;       /* accumulated arc length including laps */
    float odo;
    float lateral;
    float height;
    float half_width;
    float speed;
    float offroad_time;
    float wrong_way_time;
    uint8_t surface;
    uint8_t offroad;
    uint8_t checkpoint_flags; /* raw flags of the nearest vertex */
    uint8_t reserved;
    uint8_t checkpoint_count; /* checkpoint vertices in this course */
    uint8_t checkpoint_next;  /* expected 1-based checkpoint ordinal */
    uint16_t checkpoint_mask; /* visited ordinals, bit n-1 */
    float rival_gap;      /* nearest rival ahead, metres */
    float rival_side;     /* signed lateral offset to that rival */
    int rival_position;   /* 1-based place among rivals, 0 when none */
    int collision_count;  /* distinct contact events */
} r6_race_state;

typedef struct r6_race r6_race;

R6_API size_t r6_race_size(void);
R6_API void r6_race_config_default(r6_race_config *config);
R6_API r6_race *r6_race_init(void *storage, size_t size,
                             const r6_race_config *config);
R6_API int r6_race_reset(r6_race *race, const r6_race_config *config);
R6_API int r6_race_set_rivals(r6_race *race, const r6_rival_state *rivals,
                              size_t count);
/* Spawn count simple AI cars on the current course. The first is `spacing`
 * metres ahead of the player; each later one is another `spacing` further
 * ahead, and
 * all advance at `speed` m/s with the given lateral offset. */
R6_API int r6_race_spawn_rivals(r6_race *race, size_t count, float speed,
                                float spacing, float lateral);
R6_API int r6_race_step(r6_race *race,
                        const r6_course_vertex *vertices, size_t count,
                        int closed, const r6_vehicle_state *vehicle, float dt);
R6_API int r6_race_get_state(const r6_race *race, r6_race_state *out);

#ifdef __cplusplus
}
#endif

#endif
