/* Deterministic race state machine. No CRT, no libm, no host calls. */

#include "r6/r6_race.h"

#include "core/internal.h"

/* Approximate car footprints, in metres. */
#define R6_RACE_CAR_HALF_LENGTH 2.25f
#define R6_RACE_CAR_HALF_WIDTH 0.95f
#define R6_RACE_COLLISION_COOLDOWN 0.5f

struct r6_race {
    r6_race_config config;
    r6_race_state state;
    r6_rival_state rivals[R6_RACE_MAX_RIVALS];
    size_t rival_count;
    float collision_cooldown;
    float last_s;
    int have_last;
};

static float race_abs(float value) {
    return value < 0.0f ? -value : value;
}

static int race_finite(float value) {
    return value == value && value > -1e12f && value < 1e12f;
}

static void race_sincos(float angle, float *out_sin, float *out_cos) {
    const float pi = 3.14159265358979323846f;
    float term;
    float sine;
    float cosine;
    int i;
    while (angle > pi) {
        angle -= 2.0f * pi;
    }
    while (angle < -pi) {
        angle += 2.0f * pi;
    }
    sine = angle;
    term = angle;
    for (i = 1; i <= 6; i++) {
        float factor = -angle * angle / ((2.0f * i) * (2.0f * i + 1.0f));
        term *= factor;
        sine += term;
    }
    cosine = 1.0f;
    term = 1.0f;
    for (i = 1; i <= 6; i++) {
        float factor = -angle * angle / ((2.0f * i - 1.0f) * (2.0f * i));
        term *= factor;
        cosine += term;
    }
    *out_sin = sine;
    *out_cos = cosine;
}

size_t r6_race_size(void) {
    return sizeof(r6_race);
}

void r6_race_config_default(r6_race_config *config) {
    if (!config) {
        return;
    }
    r6_memset(config, 0, sizeof(*config));
    config->mode = R6_ENMA_MODE_BATTLE;
    config->stage = 3;              /* Series01 */
    config->course = R6_ENMA_COURSE_HAKONE;
    config->goal_odo = 100000000.0f; /* SConfigPlay default */
    config->laps = 1;
    config->countdown = 3.0f;
    config->wrong_way_limit = 2.0f;
    config->offroad_factor = 1.0f;
}

r6_race *r6_race_init(void *storage, size_t size,
                      const r6_race_config *config) {
    r6_race *race;
    if (!storage || size < sizeof(r6_race)) {
        return 0;
    }
    race = (r6_race *)storage;
    r6_memset(race, 0, sizeof(*race));
    if (config) {
        race->config = *config;
    } else {
        r6_race_config_default(&race->config);
    }
    r6_race_reset(race, 0);
    return race;
}

int r6_race_reset(r6_race *race, const r6_race_config *config) {
    r6_race_state *state;
    if (!race) {
        return R6_ERR_ARG;
    }
    if (config) {
        race->config = *config;
    }
    state = &race->state;
    r6_memset(state, 0, sizeof(*state));
    race->last_s = 0.0f;
    race->have_last = 0;
    state->lap = 1;
    state->countdown = race->config.countdown;
    if (state->countdown > 0.0f) {
        state->play_state = R6_ENMA_PLAY_COUNTDOWN;
    } else {
        state->play_state = R6_ENMA_PLAY_RUN;
        state->outcome = R6_RACE_RUNNING;
    }
    return R6_OK;
}

int r6_race_set_rivals(r6_race *race, const r6_rival_state *rivals,
                       size_t count) {
    if (!race || (!rivals && count) || count > R6_RACE_MAX_RIVALS) {
        return R6_ERR_ARG;
    }
    race->rival_count = count;
    if (count) {
        r6_memcpy(race->rivals, rivals, count * sizeof(*rivals));
    } else {
        r6_memset(race->rivals, 0, sizeof(race->rivals));
    }
    return R6_OK;
}

int r6_race_step(r6_race *race,
                 const r6_course_vertex *vertices, size_t count,
                 int closed, const r6_vehicle_state *vehicle, float dt) {
    r6_race_config *config;
    r6_race_state *state;
    r6_course_projection projection;
    float s;
    float total = 0.0f;
    float delta = 0.0f;
    float sin_yaw = 0.0f;
    float cos_yaw = 1.0f;
    int have_course = 0;
    int rc;

    if (!race || !vehicle || !race_finite(dt) || dt < 0.0f) {
        return R6_ERR_ARG;
    }
    config = &race->config;
    state = &race->state;
    if (!race_finite(vehicle->x) || !race_finite(vehicle->z) ||
        !race_finite(vehicle->odo) || !race_finite(vehicle->speed)) {
        return R6_ERR_ARG;
    }

    s = vehicle->odo;
    if (vertices && count >= 2) {
        rc = r6_course_project(vertices, count, closed, vehicle->x,
                               vehicle->z, &projection);
        if (rc != R6_OK) {
            return rc;
        }
        rc = r6_course_length(vertices, count, closed, &total);
        if (rc != R6_OK) {
            return rc;
        }
        s = projection.distance;
        have_course = 1;
        state->lateral = projection.lateral;
        state->height = projection.height;
        state->half_width = projection.half_width;
        state->surface = projection.surface;
        state->checkpoint_flags = projection.flags;
    } else {
        r6_memset(&projection, 0, sizeof(projection));
        race_sincos(vehicle->yaw, &sin_yaw, &cos_yaw);
        projection.tangent_x = cos_yaw;
        projection.tangent_z = sin_yaw;
        state->lateral = 0.0f;
        state->height = 0.0f;
        state->half_width = 0.0f;
        state->surface = 0;
        state->checkpoint_flags = 0;
    }
    state->s = s;
    state->odo = vehicle->odo;
    state->speed = vehicle->speed;

    if (!race->have_last) {
        race->last_s = s;
        race->have_last = 1;
    }

    if (state->countdown > 0.0f) {
        state->play_state = R6_ENMA_PLAY_COUNTDOWN;
        state->countdown -= dt;
        if (state->countdown <= 0.0f) {
            state->countdown = 0.0f;
            state->play_state = R6_ENMA_PLAY_RUN;
            state->outcome = R6_RACE_RUNNING;
        }
        race->last_s = s;
        return R6_OK;
    }
    if (state->outcome != R6_RACE_NONE &&
        state->outcome != R6_RACE_RUNNING &&
        state->outcome != R6_RACE_COLLISION) {
        return R6_OK;
    }

    state->play_state = R6_ENMA_PLAY_RUN;
    state->outcome = R6_RACE_RUNNING;
    state->elapsed += dt;
    state->lap_time += dt;

    if (have_course && total > 0.0f) {
        delta = s - race->last_s;
        if (delta < -total * 0.5f) {
            delta += total;
            state->lap++;
            state->last_lap = state->lap_time;
            if (state->best_lap <= 0.0f || state->last_lap < state->best_lap) {
                state->best_lap = state->last_lap;
            }
            state->lap_time = 0.0f;
        } else if (delta > total * 0.5f) {
            delta -= total;
            if (state->lap > 1) {
                state->lap--;
            }
        }
        state->progress += delta;

        if (vehicle->speed > 2.0f && delta < -0.02f) {
            state->wrong_way_time += dt;
        } else if (state->wrong_way_time > 0.0f) {
            state->wrong_way_time -= dt * 0.5f;
            if (state->wrong_way_time < 0.0f) {
                state->wrong_way_time = 0.0f;
            }
        }
        if (state->wrong_way_time >= config->wrong_way_limit &&
            config->wrong_way_limit > 0.0f) {
            state->wrong_way_time = config->wrong_way_limit;
            state->play_state = R6_ENMA_PLAY_RETIRE;
            state->outcome = R6_RACE_WRONG_WAY;
        }

        if (state->half_width > 0.0f &&
            race_abs(state->lateral) >
                state->half_width * config->offroad_factor) {
            state->offroad_time += dt;
            state->offroad = 1;
        } else {
            if (state->offroad_time > 0.0f) {
                state->offroad_time -= dt;
                if (state->offroad_time < 0.0f) {
                    state->offroad_time = 0.0f;
                }
            }
            state->offroad = 0;
        }
    } else {
        state->progress = vehicle->odo;
    }
    race->last_s = s;

    if (race->collision_cooldown > 0.0f) {
        race->collision_cooldown -= dt;
        if (race->collision_cooldown < 0.0f) {
            race->collision_cooldown = 0.0f;
        }
    }
    if (race->rival_count) {
        float best_gap = 0.0f;
        float best_side = 0.0f;
        int position = 1;
        int contact = 0;
        size_t index;
        for (index = 0; index < race->rival_count; index++) {
            const r6_rival_state *rival = &race->rivals[index];
            float dx = rival->x - vehicle->x;
            float dz = rival->z - vehicle->z;
            float forward = dx * projection.tangent_x +
                            dz * projection.tangent_z;
            float side = dx * -projection.tangent_z +
                         dz * projection.tangent_x;
            if (forward > 0.5f) {
                position++;
                if (best_gap <= 0.0f || forward < best_gap) {
                    best_gap = forward;
                    best_side = side;
                }
            }
            if (race_abs(forward) < 2.0f * R6_RACE_CAR_HALF_LENGTH &&
                race_abs(side) < 2.0f * R6_RACE_CAR_HALF_WIDTH) {
                contact = 1;
            }
        }
        state->rival_gap = best_gap;
        state->rival_side = best_side;
        state->rival_position = position;
        if (contact && race->collision_cooldown <= 0.0f &&
            state->outcome == R6_RACE_RUNNING) {
            state->collision_count++;
            race->collision_cooldown = R6_RACE_COLLISION_COOLDOWN;
            state->play_state = R6_ENMA_PLAY_SLOWDOWN;
            state->outcome = R6_RACE_COLLISION;
        }
    }

    if (state->outcome == R6_RACE_RUNNING) {
        if (config->time_limit > 0.0f &&
            state->elapsed >= config->time_limit) {
            state->elapsed = config->time_limit;
            state->play_state = R6_ENMA_PLAY_TIME_UP;
            state->outcome = R6_RACE_TIME_UP;
        } else if ((config->goal_odo > 0.0f &&
                    state->progress >= config->goal_odo) ||
                   (config->laps > 0 && state->lap > config->laps)) {
            state->play_state = R6_ENMA_PLAY_GOAL;
            state->outcome = R6_RACE_GOAL;
        }
    }

    if (!race_finite(state->progress) || !race_finite(state->elapsed) ||
        !race_finite(state->lateral) || !race_finite(state->rival_gap)) {
        float countdown = config->countdown;
        r6_memset(&race->state, 0, sizeof(race->state));
        race->state.lap = 1;
        race->state.countdown = countdown;
        race->state.play_state = countdown > 0.0f
                                     ? R6_ENMA_PLAY_COUNTDOWN
                                     : R6_ENMA_PLAY_RUN;
        race->state.outcome = countdown > 0.0f ? R6_RACE_NONE
                                               : R6_RACE_RUNNING;
        race->have_last = 0;
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_race_get_state(const r6_race *race, r6_race_state *out) {
    if (!race || !out) {
        return R6_ERR_ARG;
    }
    *out = race->state;
    return R6_OK;
}
