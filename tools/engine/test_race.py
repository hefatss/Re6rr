"""ctypes checks for the course projection and race state machine."""

import argparse
import ctypes
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_engine import R6_OK, load_core  # noqa: E402
from test_physics import Physics, State  # noqa: E402
from course_descriptor import build as build_descriptor  # noqa: E402

R6_ERR_ARG = -1
R6_RACE_NONE = 0
R6_RACE_RUNNING = 1
R6_RACE_GOAL = 2
R6_RACE_WRONG_WAY = 5
R6_RACE_COLLISION = 6
R6_PLAY_COUNTDOWN = 1
R6_PLAY_RUN = 2
R6_PLAY_RETIRE = 3
R6_PLAY_GOAL = 8

START = 2
GOAL = 4
GRAVEL = 2


class Vertex(ctypes.Structure):
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


class RaceConfig(ctypes.Structure):
    _fields_ = [
        ("mode", ctypes.c_int), ("stage", ctypes.c_int),
        ("course", ctypes.c_int), ("area", ctypes.c_int),
        ("goal_odo", ctypes.c_float), ("time_limit", ctypes.c_float),
        ("countdown", ctypes.c_float), ("laps", ctypes.c_int),
        ("wrong_way_limit", ctypes.c_float),
        ("offroad_factor", ctypes.c_float),
    ]


class RaceState(ctypes.Structure):
    _fields_ = [
        ("play_state", ctypes.c_int), ("outcome", ctypes.c_int),
        ("elapsed", ctypes.c_float), ("countdown", ctypes.c_float),
        ("lap", ctypes.c_int),
        ("lap_time", ctypes.c_float), ("last_lap", ctypes.c_float),
        ("best_lap", ctypes.c_float),
        ("s", ctypes.c_float), ("progress", ctypes.c_float),
        ("odo", ctypes.c_float), ("lateral", ctypes.c_float),
        ("height", ctypes.c_float), ("half_width", ctypes.c_float),
        ("speed", ctypes.c_float), ("offroad_time", ctypes.c_float),
        ("wrong_way_time", ctypes.c_float),
        ("surface", ctypes.c_uint8), ("offroad", ctypes.c_uint8),
        ("checkpoint_flags", ctypes.c_uint8), ("reserved", ctypes.c_uint8),
        ("rival_gap", ctypes.c_float), ("rival_side", ctypes.c_float),
        ("rival_position", ctypes.c_int), ("collision_count", ctypes.c_int),
    ]


class Rival(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float),
        ("yaw", ctypes.c_float), ("speed", ctypes.c_float),
        ("s", ctypes.c_float), ("lateral", ctypes.c_float),
        ("id", ctypes.c_uint32),
    ]


def vertex(x, z, width=5.0, surface=0, flags=0, y=0.0):
    return Vertex(x, y, z, width, surface, flags, 0)


def vehicle(x, z, speed=10.0, odo=None):
    state = State()
    state.x = x
    state.z = z
    state.speed = speed
    state.vx = speed
    state.odo = x if odo is None else odo
    state.gear = 1
    return state


class Race:
    def __init__(self, lib, config=None):
        lib.r6_race_size.restype = ctypes.c_size_t
        lib.r6_race_config_default.argtypes = [ctypes.POINTER(RaceConfig)]
        lib.r6_race_init.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.POINTER(RaceConfig)]
        lib.r6_race_init.restype = ctypes.c_void_p
        lib.r6_race_reset.argtypes = [ctypes.c_void_p,
                                      ctypes.POINTER(RaceConfig)]
        lib.r6_race_step.argtypes = [ctypes.c_void_p, ctypes.POINTER(Vertex),
                                     ctypes.c_size_t, ctypes.c_int,
                                     ctypes.POINTER(State), ctypes.c_float]
        lib.r6_race_get_state.argtypes = [ctypes.c_void_p,
                                          ctypes.POINTER(RaceState)]
        lib.r6_race_set_rivals.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(Rival),
                                           ctypes.c_size_t]
        self.lib = lib
        self.storage = ctypes.create_string_buffer(lib.r6_race_size())
        if config is None:
            config = RaceConfig()
            lib.r6_race_config_default(ctypes.byref(config))
        self.handle = lib.r6_race_init(self.storage, len(self.storage),
                                       ctypes.byref(config))

    def reset(self, config):
        self.lib.r6_race_reset(self.handle, ctypes.byref(config))

    def step(self, vertices, closed, state, dt):
        array = (Vertex * len(vertices))(*vertices) if vertices else None
        return self.lib.r6_race_step(self.handle, array, len(vertices),
                                     closed, ctypes.byref(state), dt)

    def set_rivals(self, rivals):
        array = (Rival * len(rivals))(*rivals) if rivals else None
        return self.lib.r6_race_set_rivals(self.handle, array, len(rivals))

    def state(self):
        out = RaceState()
        self.lib.r6_race_get_state(self.handle, ctypes.byref(out))
        return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                      "r6_engine.dll"))
    parser.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                         r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = load_core(args.dll, args.dump)
    failures = []

    lib.r6_course_length.argtypes = [ctypes.POINTER(Vertex), ctypes.c_size_t,
                                     ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
    lib.r6_course_project.argtypes = [ctypes.POINTER(Vertex), ctypes.c_size_t,
                                      ctypes.c_int, ctypes.c_float,
                                      ctypes.c_float,
                                      ctypes.POINTER(Projection)]
    lib.r6_course_at.argtypes = [ctypes.POINTER(Vertex), ctypes.c_size_t,
                                 ctypes.c_int, ctypes.c_float,
                                 ctypes.POINTER(ctypes.c_float * 3)]
    lib.r6_course_descriptor_parse.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(Vertex), ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
    ]

    straight = (Vertex * 2)(vertex(0, 0, 5, 0, START),
                            vertex(100, 0, 5, GRAVEL, GOAL))
    length = ctypes.c_float()
    rc = lib.r6_course_length(straight, 2, 0, ctypes.byref(length))
    if rc != R6_OK or abs(length.value - 100.0) > 1e-3:
        failures.append("straight length rc=%d len=%f" % (rc, length.value))
    else:
        print("  straight length 100 m")

    projected = Projection()
    rc = lib.r6_course_project(straight, 2, 0, 25.0, 3.0,
                               ctypes.byref(projected))
    if (rc != R6_OK or abs(projected.distance - 25.0) > 1e-3 or
            abs(projected.lateral - 3.0) > 1e-3 or
            abs(projected.tangent_x - 1.0) > 1e-3 or projected.surface != 0):
        failures.append("projection rc=%d d=%f lat=%f surf=%d" %
                        (rc, projected.distance, projected.lateral,
                         projected.surface))
    else:
        print("  projection: distance 25 m, lateral 3 m, tangent +x")

    point = (ctypes.c_float * 3)()
    if lib.r6_course_at(straight, 2, 0, 25.0, point) != R6_OK or \
            abs(point[0] - 25.0) > 1e-3:
        failures.append("course_at %r" % (list(point),))
    else:
        print("  course_at(25) = (25, 0, 0)")

    square = (Vertex * 4)(vertex(0, 0, 5, 0, START),
                          vertex(100, 0, 5),
                          vertex(100, 100, 5),
                          vertex(0, 100, 5, 0, GOAL))
    rc = lib.r6_course_length(square, 4, 1, ctypes.byref(length))
    if rc != R6_OK or abs(length.value - 400.0) > 1e-3:
        failures.append("closed length rc=%d len=%f" % (rc, length.value))
    else:
        print("  closed square length 400 m")

    descriptor, header = build_descriptor(args.dump, "FUKUOKA", 0, 6.0)
    desc_flags = ctypes.c_uint32()
    desc_count = ctypes.c_size_t(header["vertices"])
    desc_vertices = (Vertex * header["vertices"])()
    rc = lib.r6_course_descriptor_parse(
        descriptor, len(descriptor), ctypes.byref(desc_flags),
        desc_vertices, header["vertices"], ctypes.byref(desc_count))
    first = struct.unpack_from("<ffff", descriptor, 24)
    if (rc != R6_OK or desc_count.value != header["vertices"] or
            not desc_flags.value & 1 or
            abs(desc_vertices[0].x - first[0]) > 1e-4 or
            abs(desc_vertices[0].z - first[2]) > 1e-4 or
            abs(desc_vertices[0].half_width - 6.0) > 1e-4):
        failures.append("descriptor rc=%d count=%d flags=%d first=%r" %
                        (rc, desc_count.value, desc_flags.value, first))
    else:
        print("  Fukuoka descriptor: %d vertices, closed, first (%.2f, %.2f)" %
              (header["vertices"], first[0], first[2]))
    projected = Projection()
    sample = desc_vertices[50]
    rc = lib.r6_course_project(desc_vertices, desc_count.value, 1,
                               sample.x, sample.z, ctypes.byref(projected))
    if rc != R6_OK or not math.isfinite(projected.distance):
        failures.append("shipped course projection rc=%d" % rc)
    else:
        print("  shipped sample 50 projects to s=%.2f m" % projected.distance)

    config = RaceConfig()
    lib.r6_race_config_default(ctypes.byref(config))
    config.countdown = 0.0
    config.goal_odo = 0.0
    config.laps = 0
    config.time_limit = 0.0
    race = Race(lib, config)

    rc = race.step(straight, 0, vehicle(0, 0), 1.0 / 60.0)
    state = race.state()
    if rc != R6_OK or state.play_state != R6_PLAY_RUN:
        failures.append("run start rc=%d state=%d" % (rc, state.play_state))
    rc = race.step(straight, 0, vehicle(95, 8), 1.0 / 60.0)
    state = race.state()
    if rc != R6_OK or not state.offroad or state.surface != GRAVEL:
        failures.append("offroad rc=%d off=%d surf=%d" %
                        (rc, state.offroad, state.surface))
    else:
        print("  off-road detected on gravel segment")

    config.countdown = 1.0
    config.goal_odo = 50.0
    race.reset(config)
    race.step(straight, 0, vehicle(0, 0), 0.5)
    state = race.state()
    if state.play_state != R6_PLAY_COUNTDOWN or state.progress != 0.0:
        failures.append("countdown state=%d progress=%f" %
                        (state.play_state, state.progress))
    race.step(straight, 0, vehicle(0, 0), 0.5)
    state = race.state()
    if state.play_state != R6_PLAY_RUN:
        failures.append("countdown did not finish: %d" % state.play_state)
    for x in range(0, 61, 5):
        race.step(straight, 0, vehicle(x, 0), 0.1)
    state = race.state()
    if (state.outcome != R6_RACE_GOAL or state.play_state != R6_PLAY_GOAL or
            state.progress < 50.0):
        failures.append("goal outcome=%d play=%d progress=%f" %
                        (state.outcome, state.play_state, state.progress))
    else:
        print("  countdown + goal: progress %.1f m -> GOAL" % state.progress)

    config.countdown = 0.0
    config.goal_odo = 0.0
    config.laps = 0
    race.reset(config)
    race.step(square, 1, vehicle(0, 10, 10, 390), 0.1)
    race.step(square, 1, vehicle(5, 0, 10, 400), 0.1)
    state = race.state()
    if state.lap != 2 or state.best_lap <= 0.0 or state.progress < 0.0:
        failures.append("lap wrap lap=%d best=%f progress=%f" %
                        (state.lap, state.best_lap, state.progress))
    else:
        print("  lap wrap: lap 2, best lap %.1f s, progress %.1f m" %
              (state.best_lap, state.progress))

    race.reset(config)
    for index in range(12):
        x = 12 - index
        rc = race.step(square, 1, vehicle(x, 0, 10, x), 0.25)
        if rc != R6_OK:
            failures.append("wrong-way rc=%d" % rc)
            break
    state = race.state()
    if (state.outcome != R6_RACE_WRONG_WAY or
            state.play_state != R6_PLAY_RETIRE):
        failures.append("wrong-way outcome=%d play=%d time=%f" %
                        (state.outcome, state.play_state,
                         state.wrong_way_time))
    else:
        print("  sustained reverse travel -> RETIRE")

    race.reset(config)
    ahead = Rival(30.0, 0.0, 0.0, 0.0, 20.0, 30.0, 0.0, 1)
    behind = Rival(-10.0, 0.0, 2.0, 0.0, 15.0, 0.0, 2.0, 2)
    if race.set_rivals([ahead, behind]) != R6_OK:
        failures.append("set_rivals failed")
    race.step(straight, 0, vehicle(20.0, 0.0, 15.0), 1.0 / 60.0)
    state = race.state()
    if (abs(state.rival_gap - 10.0) > 1e-3 or
            abs(state.rival_side) > 1e-3 or state.rival_position != 2):
        failures.append("rival gap=%f side=%f place=%d" %
                        (state.rival_gap, state.rival_side,
                         state.rival_position))
    else:
        print("  rival: gap %.1f m, place %d" %
              (state.rival_gap, state.rival_position))
    contact = Rival(21.0, 0.0, 0.4, 0.0, 12.0, 21.0, 0.4, 3)
    race.set_rivals([contact])
    race.step(straight, 0, vehicle(20.0, 0.0, 15.0), 1.0 / 60.0)
    state = race.state()
    if state.collision_count != 1 or state.outcome != R6_RACE_COLLISION:
        failures.append("collision count=%d outcome=%d" %
                        (state.collision_count, state.outcome))
    else:
        print("  rival contact -> collision 1, SlowDown")
    race.step(straight, 0, vehicle(20.0, 0.0, 15.0), 1.0 / 60.0)
    if race.state().outcome != R6_RACE_RUNNING:
        failures.append("collision did not recover to running")
    if race.set_rivals([ahead] * 9) != R6_ERR_ARG:
        failures.append("more than 8 rivals accepted")
    race.set_rivals([])

    if race.step(straight, 0, vehicle(0, 0), -1.0) != R6_ERR_ARG:
        failures.append("negative dt accepted by race")
    if lib.r6_race_step(race.handle, None, 0, 0, None, 0.016) != R6_ERR_ARG:
        failures.append("null vehicle accepted by race")

    physics = Physics(args.dll, args.dump)
    race.reset(config)
    for _ in range(180):
        if physics.step(1.0, 0.0, 0.0) != R6_OK:
            failures.append("vehicle step failed")
            break
        vstate = physics.state()
        if race.step(straight, 0, vstate, 1.0 / 60.0) != R6_OK:
            failures.append("race step failed with vehicle")
            break
    state = race.state()
    if not math.isfinite(state.progress) or state.progress <= 0.0:
        failures.append("vehicle+race progress=%f" % state.progress)
    else:
        print("  vehicle+race: %.1f m in 3 s" % state.progress)

    if failures:
        for failure in failures:
            print("FAIL " + failure)
        return 1
    print("all course/race checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
