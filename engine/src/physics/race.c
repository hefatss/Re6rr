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
    uint8_t rival_ai[R6_RACE_MAX_RIVALS];
    int goal_vertex_count;
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

static void race_reset_checkpoints(r6_race_state *state) {
    state->checkpoint_mask = 0;
    state->checkpoint_next = 1;
}

/* Ordinal of the checkpoint nearest (x,z), in course order. The generator in
 * tools/engine/course_descriptor.py marks path-piece beginnings. */
static void race_scan_course(const r6_course_vertex *vertices, size_t count,
                            float x, float z, int *cp_count, int *goal_count,
                            int *nearest_cp) {
    size_t i;
    int ordinal = 0;
    float best_d2 = 0.0f;
    int have_best = 0;
    *cp_count = 0;
    *goal_count = 0;
    *nearest_cp = 0;
    for (i = 0; i < count; i++) {
        float dx;
        float dz;
        float d2;
        if (vertices[i].flags & R6_COURSE_CHECKPOINT) {
            ordinal++;
            if (ordinal <= R6_RACE_MAX_CHECKPOINTS) {
                (*cp_count)++;
            }
            dx = vertices[i].x - x;
            dz = vertices[i].z - z;
            d2 = dx * dx + dz * dz;
            if (!have_best || d2 < best_d2) {
                have_best = 1;
                best_d2 = d2;
                *nearest_cp = ordinal;
            }
        }
        if (vertices[i].flags & R6_COURSE_GOAL) {
            (*goal_count)++;
        }
    }
    if (!have_best || *nearest_cp > R6_RACE_MAX_CHECKPOINTS) {
        *nearest_cp = 0;
    }
}

static void race_advance_ai(r6_race *race,
                            const r6_course_vertex *vertices, size_t count,
                            int closed, float total, float dt) {
    size_t index;
    for (index = 0; index < race->rival_count; index++) {
        r6_rival_state *rival = &race->rivals[index];
        r6_course_projection projection;
        float point[3];
        if (!race->rival_ai[index]) {
            continue;
        }
        rival->s += rival->speed * dt;
        if (closed && total > 0.0f) {
            while (rival->s >= total) {
                rival->s -= total;
            }
            while (rival->s < 0.0f) {
                rival->s += total;
            }
        } else if (total > 0.0f) {
            if (rival->s < 0.0f) {
                rival->s = 0.0f;
            } else if (rival->s > total) {
                rival->s = total;
            }
        }
        if (r6_course_at(vertices, count, closed, rival->s, point) != R6_OK ||
            r6_course_project(vertices, count, closed, point[0], point[2],
                              &projection) != R6_OK) {
            continue;
        }
        rival->x = point[0] + rival->lateral * -projection.tangent_z;
        rival->y = point[1];
        rival->z = point[2] + rival->lateral * projection.tangent_x;
        rival->yaw = 0.0f; /* heading is not used by the freestanding core */
    }
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
    race->goal_vertex_count = 0;
    race_reset_checkpoints(state);
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
    r6_memset(race->rival_ai, 0, sizeof(race->rival_ai));
    if (count) {
        r6_memcpy(race->rivals, rivals, count * sizeof(*rivals));
    } else {
        r6_memset(race->rivals, 0, sizeof(race->rivals));
    }
    return R6_OK;
}

int r6_race_spawn_rivals(r6_race *race, size_t count, float speed,
                         float spacing, float lateral) {
    size_t index;
    if (!race || count > R6_RACE_MAX_RIVALS || !race_finite(speed) ||
        !race_finite(spacing) || !race_finite(lateral) || spacing < 0.0f) {
        return R6_ERR_ARG;
    }
    r6_memset(race->rivals, 0, sizeof(race->rivals));
    r6_memset(race->rival_ai, 0, sizeof(race->rival_ai));
    for (index = 0; index < count; index++) {
        r6_rival_state *rival = &race->rivals[index];
        rival->s = race->state.s + spacing * (float)(index + 1);
        rival->speed = speed;
        rival->lateral = lateral;
        rival->id = (uint32_t)(index + 1);
        race->rival_ai[index] = 1;
    }
    race->rival_count = count;
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
    int cp_count = 0;
    int goal_count = 0;
    int nearest_cp = 0;
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
        race_scan_course(vertices, count, vehicle->x, vehicle->z,
                         &cp_count, &goal_count, &nearest_cp);
        state->checkpoint_count = (uint8_t)cp_count;
        race->goal_vertex_count = goal_count;
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
        state->checkpoint_count = 0;
        race->goal_vertex_count = 0;
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
        if (closed && delta < -total * 0.5f) {
            delta += total;
            state->lap++;
            state->last_lap = state->lap_time;
            if (state->best_lap <= 0.0f || state->last_lap < state->best_lap) {
                state->best_lap = state->last_lap;
            }
            state->lap_time = 0.0f;
            race_reset_checkpoints(state);
        } else if (closed && delta > total * 0.5f) {
            delta -= total;
            if (state->lap > 1) {
                state->lap--;
            }
            race_reset_checkpoints(state);
        }
        state->progress += delta;

        if (nearest_cp > 0 &&
            (projection.flags & R6_COURSE_CHECKPOINT) != 0u &&
            nearest_cp == state->checkpoint_next) {
            state->checkpoint_mask =
                (uint16_t)(state->checkpoint_mask |
                           (1u << (nearest_cp - 1)));
            state->checkpoint_next++;
        }

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

    if (have_course && total > 0.0f) {
        race_advance_ai(race, vertices, count, closed, total, dt);
    }

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
        int checkpoints_done = state->checkpoint_count == 0 ||
                               state->checkpoint_next > state->checkpoint_count;
        if (config->time_limit > 0.0f &&
            state->elapsed >= config->time_limit) {
            state->elapsed = config->time_limit;
            state->play_state = R6_ENMA_PLAY_TIME_UP;
            state->outcome = R6_RACE_TIME_UP;
        } else if (have_course && race->goal_vertex_count > 0) {
            if (checkpoints_done &&
                ((projection.flags & R6_COURSE_GOAL) != 0u ||
                 (config->goal_odo > 0.0f &&
                  state->progress >= config->goal_odo))) {
                state->play_state = R6_ENMA_PLAY_GOAL;
                state->outcome = R6_RACE_GOAL;
            }
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
        race_reset_checkpoints(&race->state);
        race->goal_vertex_count = 0;
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
