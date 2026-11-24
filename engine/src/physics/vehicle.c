/* Deterministic freestanding vehicle model. No CRT and no host calls. */

#include "r6/r6_enma.h"
#include "r6/r6_physics.h"

#include "core/internal.h"

#define R6_PI 3.14159265358979323846f
#define R6_GRAVITY 9.81f

struct r6_vehicle {
    r6_vehicle_config config;
    r6_vehicle_state state;
};

static float clampf(float value, float low, float high) {
    if (value < low) {
        return low;
    }
    if (value > high) {
        return high;
    }
    return value;
}

static int finitef(float value) {
    return value == value && value > -1e12f && value < 1e12f;
}

static float r6_sqrtf(float value) {
    float guess;
    int i;
    if (value <= 0.0f) {
        return 0.0f;
    }
    /* Bit-level seed, then two Newton steps: enough for model quantities. */
    {
        unsigned int bits;
        r6_memcpy(&bits, &value, sizeof(bits));
        bits = (bits >> 1) + 0x1fc00000u;
        r6_memcpy(&guess, &bits, sizeof(guess));
    }
    for (i = 0; i < 3; i++) {
        guess = 0.5f * (guess + value / guess);
    }
    return guess;
}

static void r6_sincosf(float angle, float *out_sin, float *out_cos) {
    float term;
    float sine;
    float cosine;
    int i;
    while (angle > R6_PI) {
        angle -= 2.0f * R6_PI;
    }
    while (angle < -R6_PI) {
        angle += 2.0f * R6_PI;
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

size_t r6_vehicle_size(void) {
    return sizeof(r6_vehicle);
}

void r6_vehicle_config_default(r6_vehicle_config *config) {
    static const float ratios[8] = {0.0f, 3.5f, 2.2f, 1.6f,
                                    1.25f, 1.0f, 0.82f, 0.0f};
    if (!config) {
        return;
    }
    r6_memset(config, 0, sizeof(*config));
    config->mass = 1300.0f;
    config->wheelbase = 2.5f;
    config->track = 1.55f;
    config->cg_height = 0.5f;
    config->wheel_radius = 0.32f;
    config->power_w = 240000.0f;
    config->rpm_idle = 900.0f;
    config->rpm_peak = 6500.0f;
    config->rpm_limit = 7800.0f;
    r6_memcpy(config->gear_ratio, ratios, sizeof(ratios));
    config->gear_count = 6;
    config->final_drive = 3.2f;
    config->efficiency = 0.88f;
    config->brake_torque = 6000.0f;
    config->grip = 1.1f;
    config->drag_coeff = 0.45f;
    config->rolling_resistance = 0.015f;
    config->steer_max = 0.55f;
    config->corner_stiffness = 60000.0f;
    config->drive_system = R6_DRIVE_FR;
    config->transmission = R6_ENMA_AT;
}

r6_vehicle *r6_vehicle_init(void *storage, size_t size,
                            const r6_vehicle_config *config) {
    r6_vehicle *vehicle;
    if (!storage || size < sizeof(r6_vehicle)) {
        return 0;
    }
    vehicle = (r6_vehicle *)storage;
    r6_memset(vehicle, 0, sizeof(*vehicle));
    if (config) {
        vehicle->config = *config;
    } else {
        r6_vehicle_config_default(&vehicle->config);
    }
    r6_vehicle_reset(vehicle, 0);
    return vehicle;
}

int r6_vehicle_reset(r6_vehicle *vehicle, const r6_vehicle_config *config) {
    r6_vehicle_state *state;
    if (!vehicle) {
        return R6_ERR_ARG;
    }
    if (config) {
        vehicle->config = *config;
    }
    state = &vehicle->state;
    r6_memset(state, 0, sizeof(*state));
    state->gear = 1;
    state->rpm = vehicle->config.rpm_idle;
    return R6_OK;
}

static float engine_torque(const r6_vehicle_config *config, float rpm) {
    float peak_torque;
    float ratio;
    float shape;
    if (rpm <= 0.0f || config->rpm_peak <= 0.0f) {
        return 0.0f;
    }
    /* Torque peak sits below the power peak in the game's tuning range. */
    peak_torque = (config->power_w / 1000.0f) * 9549.0f /
                  config->rpm_peak * 1.15f;
    ratio = rpm / config->rpm_peak;
    if (ratio <= 1.0f) {
        shape = 0.70f + 0.30f * ratio;
    } else {
        float span = config->rpm_limit - config->rpm_peak;
        float over = span > 1.0f ? (rpm - config->rpm_peak) / span : 1.0f;
        shape = 1.0f - 0.6f * over * over;
    }
    return peak_torque * clampf(shape, 0.2f, 1.0f);
}

static int apply_gear(r6_vehicle *vehicle, int command) {
    const r6_vehicle_config *config = &vehicle->config;
    int gear = vehicle->state.gear;
    if (config->transmission == R6_ENMA_AT || command == R6_GEAR_AUTO) {
        return R6_OK;
    }
    if (command == R6_GEAR_UP) {
        gear++;
    } else if (command == R6_GEAR_DOWN) {
        gear--;
    } else if (command >= 1 && command <= config->gear_count) {
        gear = command;
    }
    if (gear < 1 || gear > config->gear_count) {
        return R6_ERR_ARG;
    }
    vehicle->state.gear = gear;
    return R6_OK;
}

int r6_vehicle_step(r6_vehicle *vehicle, float throttle, float brake,
                    float steer, int gear_command, float dt) {
    r6_vehicle_config *config;
    r6_vehicle_state *state;
    float substeps;
    float step;
    int i;
    int rc;

    if (!vehicle || dt < 0.0f) {
        return R6_ERR_ARG;
    }
    if (!finitef(dt)) {
        return R6_ERR_ARG;
    }
    rc = apply_gear(vehicle, gear_command);
    if (rc != R6_OK) {
        return rc;
    }
    config = &vehicle->config;
    state = &vehicle->state;
    throttle = clampf(throttle, 0.0f, 1.0f);
    brake = clampf(brake, 0.0f, 1.0f);
    steer = clampf(steer, -1.0f, 1.0f);
    state->throttle = throttle;
    state->brake = brake;
    state->steer = steer;
    if (config->gear_count < 1 || config->gear_count > 7 ||
        config->wheel_radius <= 0.0f || config->mass <= 0.0f) {
        return R6_ERR_ARG;
    }

    substeps = dt > 0.0083334f ? r6_sqrtf(dt * 120.0f) : 1.0f;
    if (substeps < 1.0f) {
        substeps = 1.0f;
    }
    if (substeps > 16.0f) {
        substeps = 16.0f;
    }
    step = dt / substeps;

    for (i = 0; i < (int)substeps; i++) {
        float ratio = config->gear_ratio[state->gear] * config->final_drive;
        float speed = r6_sqrtf(state->vx * state->vx + state->vy * state->vy);
        float wheel_rps = speed / (2.0f * R6_PI * config->wheel_radius);
        float drive_force = 0.0f;
        float brake_force = 0.0f;
        float resistance;
        float accel;
        float steer_angle;
        float alpha_front;
        float alpha_rear;
        float front_force;
        float rear_force;
        float grip_front;
        float grip_rear;
        float half_wheelbase = config->wheelbase * 0.5f;
        float inertia = config->mass *
                        (config->wheelbase * config->wheelbase +
                         config->track * config->track) / 12.0f;
        float cos_yaw;
        float sin_yaw;

        state->rpm = clampf(wheel_rps * ratio * 60.0f,
                            config->rpm_idle, config->rpm_limit);
        if (config->transmission == R6_ENMA_AT) {
            if (state->rpm > config->rpm_limit * 0.94f &&
                state->gear < config->gear_count) {
                state->gear++;
            } else if (state->rpm < config->rpm_idle * 1.8f &&
                       state->gear > 1) {
                state->gear--;
            }
            ratio = config->gear_ratio[state->gear] * config->final_drive;
            state->rpm = clampf(wheel_rps * ratio * 60.0f,
                                config->rpm_idle, config->rpm_limit);
        }

        drive_force = engine_torque(config, state->rpm) * ratio *
                      config->efficiency / config->wheel_radius * throttle;
        if (drive_force > config->grip * config->mass * R6_GRAVITY) {
            drive_force = config->grip * config->mass * R6_GRAVITY;
        }

        brake_force = config->brake_torque * brake / config->wheel_radius;
        if (brake_force > speed * config->mass / (step > 0.0f ? step : 1.0f)) {
            brake_force = speed * config->mass / (step > 0.0f ? step : 1.0f);
        }
        resistance = config->drag_coeff * speed * speed +
                     config->mass * R6_GRAVITY * config->rolling_resistance;
        accel = (drive_force - brake_force - resistance) / config->mass;
        if (state->vx < 0.0f) {
            accel += 2.0f * resistance / config->mass;
        }
        state->vx += accel * step;
        if (state->vx < 0.0f && (throttle > 0.0f || brake == 0.0f)) {
            state->vx = 0.0f;
        }
        state->wheel_spin += state->vx / config->wheel_radius * step;

        steer_angle = steer * config->steer_max /
                      (1.0f + 0.9f * clampf(speed / 60.0f, 0.0f, 1.0f));
        {
            float longitudinal = state->vx > 1.0f ? state->vx : 1.0f;
            alpha_front = (state->vy + half_wheelbase * state->yaw_rate) /
                          longitudinal - steer_angle;
            alpha_rear = (state->vy - half_wheelbase * state->yaw_rate) /
                         longitudinal;
        }
        front_force = -config->corner_stiffness * alpha_front;
        rear_force = -config->corner_stiffness * alpha_rear;
        grip_front = config->grip * config->mass * R6_GRAVITY * 0.55f;
        grip_rear = config->grip * config->mass * R6_GRAVITY * 0.45f;
        front_force = clampf(front_force, -grip_front, grip_front);
        rear_force = clampf(rear_force, -grip_rear, grip_rear);

        state->vy += ((front_force + rear_force) / config->mass -
                      state->vx * state->yaw_rate) * step;
        state->yaw_rate += ((half_wheelbase * front_force -
                             half_wheelbase * rear_force) / inertia) * step;
        state->yaw += state->yaw_rate * step;

        r6_sincosf(state->yaw, &sin_yaw, &cos_yaw);
        state->x += (state->vx * cos_yaw - state->vy * sin_yaw) * step;
        state->z += (state->vx * sin_yaw + state->vy * cos_yaw) * step;
        state->odo += speed * step;
        if (state->yaw > R6_PI) {
            state->yaw -= 2.0f * R6_PI;
        } else if (state->yaw < -R6_PI) {
            state->yaw += 2.0f * R6_PI;
        }
    }

    state->speed = r6_sqrtf(state->vx * state->vx + state->vy * state->vy);
    if (!finitef(state->vx) || !finitef(state->vy) ||
        !finitef(state->yaw) || !finitef(state->x) || !finitef(state->z)) {
        float gear = (float)state->gear;
        r6_memset(state, 0, sizeof(*state));
        state->gear = (int)gear;
        state->rpm = config->rpm_idle;
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_vehicle_get_state(const r6_vehicle *vehicle,
                         r6_vehicle_state *out) {
    if (!vehicle || !out) {
        return R6_ERR_ARG;
    }
    *out = vehicle->state;
    return R6_OK;
}
