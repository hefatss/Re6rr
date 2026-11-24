/* Build a vehicle config from the ordered car context already loaded in the
 * Lua host. Every getter is optional: missing values keep the safe default. */

#include "r6/r6.h"
#include "r6/r6_physics.h"

#include "core/internal.h"

static float number_or(r6_engine *engine, const char *name, float fallback) {
    double value = 0.0;
    if (r6_engine_call_number(engine, name, &value) == R6_OK && value > 0.0) {
        return (float)value;
    }
    return fallback;
}

static int gear_count_from_mission(float mission) {
    if (mission <= 1.5f) {
        return 5;
    }
    if (mission <= 2.5f) {
        return 6;
    }
    if (mission <= 3.5f) {
        return 7;
    }
    return 6;
}

int r6_vehicle_config_from_lua(r6_engine *engine, const char *tire_car,
                               const char *spec_model,
                               r6_vehicle_config *out) {
    r6_vehicle_config config;
    float positions[4][3];
    float horsepower;
    float outside_front;
    float outside_rear;
    float front_z;
    float rear_z;
    int i;
    int have_tires = 1;

    if (!engine || !out) {
        return R6_ERR_ARG;
    }
    r6_vehicle_config_default(&config);
    if (!tire_car) {
        tire_car = "";
    }

    horsepower = number_or(engine, "GetHorsepower1st", 240.0f);
    config.power_w = horsepower * 735.49875f;
    /* No mass field exists in CarDataList. This is an explicit approximation,
     * not a value recovered from the dump; callers can override it. */
    config.mass = 900.0f + horsepower * 1.2f;

    outside_front = number_or(engine, "GetTireOutsideFront", 63.1f);
    outside_rear = number_or(engine, "GetTireOutsideRear", 63.1f);
    /* TireOutside is the outer diameter in decimetres in the dump. */
    config.wheel_radius = (outside_front + outside_rear) / 40.0f;

    config.gear_count = gear_count_from_mission(
        number_or(engine, "GetMissionNumber", 2.0f));
    config.drive_system = (int)number_or(engine, "GetDriveSystem", 0.0f);

    for (i = 0; i < 4; i++) {
        if (r6_engine_call_vec3_key(engine, "GetTirePos", tire_car, i,
                                    positions[i]) != R6_OK) {
            have_tires = 0;
            break;
        }
    }
    if (have_tires) {
        front_z = (positions[0][2] + positions[1][2]) * 0.5f;
        rear_z = (positions[2][2] + positions[3][2]) * 0.5f;
        if (front_z < rear_z) {
            front_z = (positions[2][2] + positions[3][2]) * 0.5f;
            rear_z = (positions[0][2] + positions[1][2]) * 0.5f;
        }
        if (front_z - rear_z > 1.0f) {
            config.wheelbase = (front_z - rear_z) / 10.0f;
            config.track = (positions[0][2] > positions[2][2]
                            ? (positions[0][0] > 0.0f ? positions[0][0]
                                                      : -positions[0][0]) +
                              (positions[1][0] > 0.0f ? positions[1][0]
                                                      : -positions[1][0])
                            : (positions[2][0] > 0.0f ? positions[2][0]
                                                      : -positions[2][0]) +
                              (positions[3][0] > 0.0f ? positions[3][0]
                                                      : -positions[3][0])) / 10.0f;
        }
    }
    (void)spec_model;
    *out = config;
    return R6_OK;
}
