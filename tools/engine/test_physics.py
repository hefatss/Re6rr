"""ctypes checks for the freestanding vehicle model."""

import argparse
import ctypes
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_engine import Engine, R6_OK, load_core  # noqa: E402

R6_ERR_ARG = -1
R6_ERR_FORMAT = -5

MAX_GEARS = 8


class Config(ctypes.Structure):
    _fields_ = [
        ("mass", ctypes.c_float),
        ("wheelbase", ctypes.c_float),
        ("track", ctypes.c_float),
        ("cg_height", ctypes.c_float),
        ("wheel_radius", ctypes.c_float),
        ("power_w", ctypes.c_float),
        ("rpm_idle", ctypes.c_float),
        ("rpm_peak", ctypes.c_float),
        ("rpm_limit", ctypes.c_float),
        ("gear_ratio", ctypes.c_float * MAX_GEARS),
        ("gear_count", ctypes.c_int),
        ("final_drive", ctypes.c_float),
        ("efficiency", ctypes.c_float),
        ("brake_torque", ctypes.c_float),
        ("grip", ctypes.c_float),
        ("drag_coeff", ctypes.c_float),
        ("rolling_resistance", ctypes.c_float),
        ("steer_max", ctypes.c_float),
        ("corner_stiffness", ctypes.c_float),
        ("drive_system", ctypes.c_int),
        ("transmission", ctypes.c_int),
    ]


class State(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float),
        ("vx", ctypes.c_float), ("vy", ctypes.c_float),
        ("yaw", ctypes.c_float), ("yaw_rate", ctypes.c_float),
        ("speed", ctypes.c_float), ("rpm", ctypes.c_float),
        ("throttle", ctypes.c_float), ("brake", ctypes.c_float),
        ("steer", ctypes.c_float),
        ("gear", ctypes.c_int), ("odo", ctypes.c_float),
        ("wheel_spin", ctypes.c_float),
    ]


class CourseVertex(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float),
        ("half_width", ctypes.c_float),
        ("surface", ctypes.c_uint8), ("flags", ctypes.c_uint8),
        ("reserved", ctypes.c_uint16),
    ]


class Projection(ctypes.Structure):
    _fields_ = [
        ("distance", ctypes.c_float), ("lateral", ctypes.c_float),
        ("tangent_x", ctypes.c_float), ("tangent_z", ctypes.c_float),
        ("height", ctypes.c_float), ("half_width", ctypes.c_float),
        ("surface", ctypes.c_uint8), ("flags", ctypes.c_uint8),
        ("segment", ctypes.c_size_t),
    ]


class Physics:
    def __init__(self, dll, dump):
        lib = load_core(dll, dump)
        self.lib = lib
        lib.r6_vehicle_size.restype = ctypes.c_size_t
        lib.r6_vehicle_config_default.argtypes = [ctypes.POINTER(Config)]
        lib.r6_vehicle_init.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(Config)]
        lib.r6_vehicle_init.restype = ctypes.c_void_p
        lib.r6_vehicle_reset.argtypes = [ctypes.c_void_p,
                                         ctypes.POINTER(Config)]
        lib.r6_vehicle_step.argtypes = [ctypes.c_void_p, ctypes.c_float,
                                        ctypes.c_float, ctypes.c_float,
                                        ctypes.c_int, ctypes.c_float]
        lib.r6_vehicle_get_state.argtypes = [ctypes.c_void_p,
                                             ctypes.POINTER(State)]
        lib.r6_course_project.argtypes = [
            ctypes.POINTER(CourseVertex), ctypes.c_size_t, ctypes.c_int,
            ctypes.c_float, ctypes.c_float, ctypes.POINTER(Projection)]
        lib.r6_vehicle_clamp_to_course.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(CourseVertex), ctypes.c_size_t,
            ctypes.c_int]
        lib.r6_vehicle_config_from_lua.argtypes = [ctypes.c_void_p,
                                                   ctypes.c_char_p,
                                                   ctypes.c_char_p,
                                                   ctypes.POINTER(Config)]
        self.storage = ctypes.create_string_buffer(lib.r6_vehicle_size())
        config = Config()
        lib.r6_vehicle_config_default(ctypes.byref(config))
        self.handle = lib.r6_vehicle_init(self.storage, len(self.storage),
                                          ctypes.byref(config))

    def step(self, throttle, brake, steer, gear=0, dt=1.0 / 60.0):
        return self.lib.r6_vehicle_step(self.handle, throttle, brake, steer,
                                        gear, dt)

    def state(self):
        out = State()
        self.lib.r6_vehicle_get_state(self.handle, ctypes.byref(out))
        return out

    def reset(self):
        self.lib.r6_vehicle_reset(self.handle, None)


def drive(physics, frames, throttle, brake=0.0, steer=0.0):
    for _ in range(frames):
        rc = physics.step(throttle, brake, steer)
        if rc != R6_OK:
            raise AssertionError("step rc=%d" % rc)
    return physics.state()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                      "r6_engine.dll"))
    parser.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                         r"D:\Games\W6W-05"))
    args = parser.parse_args()
    failures = []
    physics = Physics(args.dll, args.dump)

    state = drive(physics, 120, 0.0)
    if abs(state.speed) > 1e-6 or abs(state.x) > 1e-6:
        failures.append("idle moved: speed=%f x=%f" % (state.speed, state.x))
    else:
        print("  idle: no movement")

    if physics.step(0.0, 0.0, 0.0, 0, -1.0) != R6_ERR_ARG:
        failures.append("negative dt accepted")
    if physics.step(0.0, 0.0, 0.0, 0, float("nan")) != R6_ERR_ARG:
        failures.append("NaN dt accepted")
    print("  invalid dt rejected")

    physics.reset()
    state = drive(physics, 480, 1.0)
    top_speed = state.speed
    if not (20.0 < top_speed < 100.0) or not math.isfinite(state.x):
        failures.append("acceleration: speed=%f x=%f" % (top_speed, state.x))
    else:
        print("  8s full throttle: %.1f m/s, gear %d, odo %.1f m" %
              (top_speed, state.gear, state.odo))
    if state.gear < 2:
        failures.append("automatic gearbox never upshifted")

    state = drive(physics, 120, 0.0, 1.0)
    if state.speed >= top_speed - 1.0:
        failures.append("brake did not slow the car: %f -> %f" %
                        (top_speed, state.speed))
    else:
        print("  2s braking: %.1f -> %.1f m/s" % (top_speed, state.speed))

    physics.reset()
    drive(physics, 120, 1.0)
    state = drive(physics, 120, 0.5, 0.0, 0.8)
    if abs(state.yaw) < 0.05:
        failures.append("steering produced no yaw: %f" % state.yaw)
    else:
        print("  steering: yaw %.3f rad, yaw_rate %.3f rad/s" %
              (state.yaw, state.yaw_rate))

    physics.reset()
    road = (CourseVertex * 2)(
        CourseVertex(-100.0, 0.0, 0.0, 2.0, 0, 0, 0),
        CourseVertex(100.0, 0.0, 0.0, 2.0, 0, 0, 0))
    for _ in range(240):
        if physics.step(1.0, 0.0, 0.9) != R6_OK:
            failures.append("clamp drive step failed")
            break
        if physics.lib.r6_vehicle_clamp_to_course(
                physics.handle, road, 2, 0) != R6_OK:
            failures.append("clamp_to_course failed")
            break
    state = physics.state()
    projection = Projection()
    physics.lib.r6_course_project(road, 2, 0, state.x, state.z,
                                  ctypes.byref(projection))
    if abs(projection.lateral) > 2.01 or not math.isfinite(state.x):
        failures.append("car left road: lateral=%f x=%f" %
                        (projection.lateral, state.x))
    else:
        print("  road wall: lateral %.3f m in 2 m half-width road" %
              projection.lateral)

    physics.reset()
    for frame in range(600):
        throttle = 1.0 if frame % 120 < 80 else 0.0
        brake = 1.0 if frame % 120 > 100 else 0.0
        steer = math.sin(frame * 0.07) * 0.6
        rc = physics.step(throttle, brake, steer)
        if rc != R6_OK:
            failures.append("mixed input rc=%d at %d" % (rc, frame))
            break
    state = physics.state()
    if not all(math.isfinite(value) for value in
               (state.x, state.z, state.vx, state.vy, state.yaw,
                state.yaw_rate, state.speed, state.rpm)):
        failures.append("mixed input produced non-finite state")
    else:
        print("  600 mixed frames finite: x=%.1f z=%.1f speed=%.1f" %
              (state.x, state.z, state.speed))

    engine = Engine(args.dll, args.dump)
    try:
        engine.setting_const()
        sets = []
        sys.path.insert(0, os.path.join(ROOT, "tools", "engine"))
        from contexts import context
        for _name, paths in context(args.dump, "CRC_928GT_Masaki",
                                    "PLC_928GT"):
            sets.extend(paths)
        rc, _message = engine.context(sets)
        if rc != R6_OK:
            failures.append("Lua context load rc=%d" % rc)
        else:
            config = Config()
            rc = physics.lib.r6_vehicle_config_from_lua(
                engine.handle, b"CRC_928GT_Masaki", b"PLC_928GT",
                ctypes.byref(config))
            if rc != R6_OK:
                failures.append("config_from_lua rc=%d" % rc)
            else:
                expected_power = 330.0 * 735.49875
                if abs(config.power_w - expected_power) > 1.0:
                    failures.append("power %f != %f" %
                                    (config.power_w, expected_power))
                if not (2.4 < config.wheelbase < 2.6):
                    failures.append("wheelbase %f" % config.wheelbase)
                if not (1.4 < config.track < 1.7):
                    failures.append("track %f" % config.track)
                if not (0.30 < config.wheel_radius < 0.34):
                    failures.append("wheel radius %f" % config.wheel_radius)
                if config.gear_count != 5:
                    failures.append("gear count %d" % config.gear_count)
                print("  Lua config: %.0f W, wheelbase %.3f m, track %.3f m, "
                      "radius %.3f m, %d gears" %
                      (config.power_w, config.wheelbase, config.track,
                       config.wheel_radius, config.gear_count))
                physics.lib.r6_vehicle_reset(physics.handle,
                                             ctypes.byref(config))
                state = drive(physics, 480, 1.0)
                print("  real car config: 8s speed %.1f m/s" % state.speed)
                if not (10.0 < state.speed < 100.0):
                    failures.append("real car speed %f" % state.speed)
    finally:
        engine.close()

    if failures:
        for failure in failures:
            print("FAIL " + failure)
        return 1
    print("all physics checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
