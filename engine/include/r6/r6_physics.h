/* Freestanding vehicle dynamics for the engine core.
 *
 * The shipped game delegates racing to yt::CSeq in Wg6Enma_Release_IDL0.dll.
 * That DLL needs host state we do not have, so this module is an original
 * deterministic model driven by the same data the game feeds it: car
 * specification Lua getters and the four tire positions. It is deliberately
 * separate from the Lua/asset core and uses no CRT, files or WinAPI.
 */
#ifndef R6_PHYSICS_H
#define R6_PHYSICS_H

#include <stddef.h>

#include "r6/r6.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Drive-system values from CarDataList.DriveSystem in the specification Lua. */
enum r6_drive_system {
    R6_DRIVE_FR = 0,
    R6_DRIVE_RR = 1,
    R6_DRIVE_MR = 2,
    R6_DRIVE_4WD = 3
};

enum r6_gear_command {
    R6_GEAR_AUTO = 0,
    R6_GEAR_DOWN = -1,
    R6_GEAR_UP = 1
};

typedef struct r6_vehicle_config {
    float mass;          /* kg */
    float wheelbase;     /* m */
    float track;         /* m */
    float cg_height;     /* m */
    float wheel_radius;  /* m */
    float power_w;       /* peak engine power, W */
    float rpm_idle;
    float rpm_peak;
    float rpm_limit;
    float gear_ratio[8];
    int gear_count;
    float final_drive;
    float efficiency;
    float brake_torque;  /* N*m at the wheels, total */
    float grip;          /* friction coefficient */
    float drag_coeff;    /* N / (m/s)^2 */
    float rolling_resistance;
    float steer_max;     /* rad at the road wheels */
    float corner_stiffness; /* N/rad per axle */
    int drive_system;
    int transmission;    /* 0 AT, 1 MT */
} r6_vehicle_config;

typedef struct r6_vehicle_state {
    float x, y, z;       /* world position, m */
    float vx, vy;        /* body-frame longitudinal / lateral velocity, m/s */
    float yaw, yaw_rate; /* rad, rad/s */
    float speed;         /* m/s */
    float rpm;
    float throttle, brake, steer;
    int gear;
    float odo;           /* m */
    float wheel_spin;    /* rad */
} r6_vehicle_state;

typedef struct r6_vehicle r6_vehicle;

R6_API size_t r6_vehicle_size(void);
R6_API void r6_vehicle_config_default(r6_vehicle_config *config);
R6_API r6_vehicle *r6_vehicle_init(void *storage, size_t size,
                                   const r6_vehicle_config *config);
R6_API int r6_vehicle_reset(r6_vehicle *vehicle,
                            const r6_vehicle_config *config);
R6_API int r6_vehicle_step(r6_vehicle *vehicle, float throttle, float brake,
                           float steer, int gear_command, float dt);
R6_API int r6_vehicle_get_state(const r6_vehicle *vehicle,
                                r6_vehicle_state *out);

/* Fill a config from the loaded car context. GetTirePos uses decimetres in
 * the dump. tire_car is the CRC_* name, spec_model the PLC_* model code. */
R6_API int r6_vehicle_config_from_lua(r6_engine *engine,
                                      const char *tire_car,
                                      const char *spec_model,
                                      r6_vehicle_config *out);

#ifdef __cplusplus
}
#endif

#endif
