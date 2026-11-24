"""ctypes checks for P5 game flow and the Enma SConfigPlay byte contract."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_engine import R6_OK, load_core  # noqa: E402
from test_race import RaceState  # noqa: E402

R6_ERR_ARG = -1
R6_ERR_STATE = -8
R6_ERR_BUFFER = -6

SELECT_CAR = 1
SELECT_COURSE = 2
RACE = 3
RESULT = 4

MODE = 4                  # R6_ENMA_MODE_BATTLE
STAGE = 3
AREA = 1
COURSE = 1
MODE_OFFSET = 0x070
STAGE_OFFSET = 0x450
AREA_OFFSET = 0x454
AZ_OFFSET = 0x458
GOAL_OFFSET = 0x45c
CFG_SIZE = 1124


class GameConfig(ctypes.Structure):
    _fields_ = [
        ("mode", ctypes.c_int), ("stage", ctypes.c_int),
        ("area", ctypes.c_int), ("course", ctypes.c_int),
        ("car_index", ctypes.c_int), ("rival_count", ctypes.c_int),
        ("start_az", ctypes.c_float), ("goal_odo", ctypes.c_float),
        ("time_limit", ctypes.c_float), ("countdown", ctypes.c_float),
        ("laps", ctypes.c_int),
    ]


class Game:
    def __init__(self, lib):
        self.lib = lib
        lib.r6_game_size.restype = ctypes.c_size_t
        lib.r6_game_config_default.argtypes = [ctypes.POINTER(GameConfig)]
        lib.r6_game_init.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.POINTER(GameConfig)]
        lib.r6_game_init.restype = ctypes.c_void_p
        lib.r6_game_get_config.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(GameConfig)]
        lib.r6_game_set_config.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(GameConfig)]
        lib.r6_game_phase.argtypes = [ctypes.c_void_p]
        lib.r6_game_phase.restype = ctypes.c_int
        lib.r6_game_select_car.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.r6_game_select_course.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                              ctypes.c_int, ctypes.c_int]
        lib.r6_game_start.argtypes = [ctypes.c_void_p]
        lib.r6_game_step.argtypes = [ctypes.c_void_p, ctypes.c_float,
                                     ctypes.POINTER(RaceState)]
        lib.r6_game_reset.argtypes = [ctypes.c_void_p]
        lib.r6_game_write_config.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                             ctypes.c_size_t]
        lib.r6_game_read_config.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_size_t]
        self.storage = ctypes.create_string_buffer(lib.r6_game_size())
        config = GameConfig()
        lib.r6_game_config_default(ctypes.byref(config))
        self.config = config
        self.handle = lib.r6_game_init(self.storage, len(self.storage),
                                       ctypes.byref(config))
        if not self.handle:
            raise AssertionError("r6_game_init returned null")

    def config_now(self):
        out = GameConfig()
        rc = self.lib.r6_game_get_config(self.handle, ctypes.byref(out))
        if rc != R6_OK:
            raise AssertionError("get_config rc=%d" % rc)
        return out

    def write(self, size=CFG_SIZE):
        blob = ctypes.create_string_buffer(size)
        rc = self.lib.r6_game_write_config(self.handle, blob, size)
        return rc, blob.raw

    def read(self, blob):
        return self.lib.r6_game_read_config(self.handle, blob, len(blob))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                      "r6_engine.dll"))
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = load_core(args.dll, args.dump)
    failures = []

    game = Game(lib)
    if lib.r6_game_phase(game.handle) != SELECT_CAR:
        failures.append("init phase is not select-car")
    else:
        print("  init phase: select car")

    if lib.r6_game_select_car(game.handle, 7) != R6_OK:
        failures.append("car select rejected")
    if lib.r6_game_select_car(game.handle, -1) != R6_ERR_ARG:
        failures.append("negative car index accepted")
    if lib.r6_game_start(game.handle) != R6_ERR_STATE:
        failures.append("race start accepted without course")
    if lib.r6_game_select_course(game.handle, COURSE, AREA, STAGE) != R6_OK:
        failures.append("course select rejected")
    if lib.r6_game_phase(game.handle) != SELECT_COURSE:
        failures.append("course phase wrong")
    if lib.r6_game_start(game.handle) != R6_OK:
        failures.append("race start rejected")
    if lib.r6_game_phase(game.handle) != RACE:
        failures.append("race phase wrong")
    else:
        print("  car 7 -> course %d area %d -> race" % (COURSE, AREA))

    state = RaceState()
    state.outcome = 0
    if lib.r6_game_step(game.handle, 0.5, ctypes.byref(state)) != R6_OK:
        failures.append("race step failed")
    if lib.r6_game_phase(game.handle) != RACE:
        failures.append("running race left race phase")
    state.outcome = 2                      # R6_RACE_GOAL
    state.elapsed = 93.5
    if lib.r6_game_step(game.handle, 0.0, ctypes.byref(state)) != R6_OK:
        failures.append("goal step failed")
    if lib.r6_game_phase(game.handle) != RESULT:
        failures.append("goal did not enter result phase")
    else:
        print("  goal enters result phase")
    if lib.r6_game_start(game.handle) != R6_ERR_STATE:
        failures.append("start accepted from result phase")
    if lib.r6_game_reset(game.handle) != R6_OK or \
            lib.r6_game_phase(game.handle) != SELECT_CAR:
        failures.append("reset did not return to select-car")

    rc, blob = game.write()
    mode = struct.unpack_from("<i", blob, MODE_OFFSET)[0]
    stage = struct.unpack_from("<i", blob, STAGE_OFFSET)[0]
    area = struct.unpack_from("<i", blob, AREA_OFFSET)[0]
    az, goal = struct.unpack_from("<ff", blob, AZ_OFFSET)
    if (rc != R6_OK or mode != MODE or stage != STAGE or area != AREA or
            az != game.config.start_az or goal != game.config.goal_odo):
        failures.append("write config: mode=%d stage=%d area=%d az=%f goal=%f" %
                        (mode, stage, area, az, goal))
    else:
        print("  SConfigPlay bytes: mode@0x70=%d stage@0x450=%d area@0x454=%d"
              % (mode, stage, area))
    if game.write(CFG_SIZE - 1)[0] != R6_ERR_BUFFER:
        failures.append("short config buffer accepted")

    changed = GameConfig()
    changed.mode = 5                       # TIME_ATTACK
    changed.stage = 9
    changed.area = 4
    changed.course = 2
    changed.car_index = 7
    changed.rival_count = 0
    changed.start_az = 12.5
    changed.goal_odo = 40000.0
    changed.time_limit = 120.0
    changed.countdown = 0.0
    changed.laps = 3
    if lib.r6_game_set_config(game.handle, ctypes.byref(changed)) != R6_OK:
        failures.append("set_config rejected")
    rc, blob = game.write()
    if (struct.unpack_from("<i", blob, MODE_OFFSET)[0] != 5 or
            struct.unpack_from("<i", blob, STAGE_OFFSET)[0] != 9 or
            struct.unpack_from("<i", blob, AREA_OFFSET)[0] != 4 or
            abs(struct.unpack_from("<f", blob, AZ_OFFSET)[0] - 12.5) > 1e-4 or
            abs(struct.unpack_from("<f", blob, GOAL_OFFSET)[0] - 40000.0) > 1e-3):
        failures.append("config changes not serialized")
    else:
        print("  round-trip: mode 5, stage 9, area 4, start 12.5 m, goal 40000 m")

    if game.read(ctypes.create_string_buffer(blob)) != R6_OK:
        failures.append("read_config rejected")
    restored = game.config_now()
    if (restored.mode != 5 or restored.stage != 9 or restored.area != 4 or
            restored.car_index != 7 or abs(restored.start_az - 12.5) > 1e-4 or
            abs(restored.goal_odo - 40000.0) > 1e-3 or
            restored.countdown != 0.0 or restored.laps != 3):
        failures.append("config read-back mismatch: %r" % (restored,))
    else:
        print("  read-back preserves non-serialized fields too")
    short = ctypes.create_string_buffer(blob[:CFG_SIZE - 1], CFG_SIZE - 1)
    if game.read(short) != R6_ERR_BUFFER:
        failures.append("short read buffer accepted")

    if failures:
        for item in failures:
            print("FAIL %s" % item)
        return 1
    print("all game checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
