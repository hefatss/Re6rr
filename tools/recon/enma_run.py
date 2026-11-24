"""Black-box drive of the shipped Enma simulation.

Feeds CGameInput (offsets recovered in enma_sim.py) into yt::CSeq and dumps
the public output structs. Used as behavioural evidence for the P4 model.
"""

import argparse
import ctypes
import json
import os
import struct

DLL_NAME = "Wg6Enma_Release_IDL0.dll"
SIZE = 8192

INIT = "?Init@CSeq@yt@@SAXAEBUSConfigPlay@@@Z"
EXEC = "?Exec@CSeq@yt@@SAXPEBVCGameInput@@@Z"
END = "?End@CSeq@yt@@SAXXZ"
SET_DEFAULT = "?SetDefault@SConfigPlay@@QEAAXXZ"
GET_PLAY_STATE = "?GetPlayState@CSeq@yt@@SAXPEAUSPlayState@@@Z"
GET_2D_RACE = "?Get2DInfoRace@CSeq@yt@@SA_NPEAUS2DInfoRace@@@Z"
GET_PLAY_RESULT = "?GetPlayResult@CSeq@yt@@SA_NPEAUSPlayResult@@@Z"
GET_MY_CAR = "?GetInfoMyCarDisp@CSeq@yt@@SA_NPEAUSInfoCarDisp@@PEAUSInfoCarEffect@@@Z"


def call(dll, name, *args):
    func = getattr(dll, name)
    func.argtypes = [ctypes.c_void_p] * len(args)
    return func(*args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    parser.add_argument("--out", default="docs/recon/enma_run.json")
    parser.add_argument("--frames", type=int, default=120)
    args = parser.parse_args()

    os.chdir(args.dump)
    dll = ctypes.CDLL(os.path.join(args.dump, DLL_NAME))
    try:
        getattr(dll, "?ForEnmaReleaseBuild@@YAXXZ")()
        print("ForEnmaReleaseBuild ok")
    except Exception as exc:
        print("ForEnmaReleaseBuild failed:", exc)
    config = (ctypes.c_ubyte * SIZE)()
    call(dll, SET_DEFAULT, config)
    # Offsets recovered from FUN_1407a9c80 (RacelibEnma.cpp) in the exe.
    struct.pack_into("<i", config, 0x000, 10)    # MyCar.CarInfo.eCarType = FD3S
    struct.pack_into("<i", config, 0x070, 4)     # eMode = Battle
    struct.pack_into("<i", config, 0x450, 3)     # RaceField.eStage = Series01
    struct.pack_into("<i", config, 0x454, 1)     # eStartAreaId
    call(dll, INIT, config)

    result = {"frames": args.frames, "traces": []}
    for accel, brake, steer in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                                (1.0, 0.0, 1.0)):
        call(dll, END)
        call(dll, INIT, config)
        frame = {"input": [accel, brake, steer], "samples": []}
        for step in range(args.frames):
            inp = (ctypes.c_ubyte * SIZE)()
            struct.pack_into("<f", inp, 0, accel)
            struct.pack_into("<f", inp, 4, brake)
            struct.pack_into("<f", inp, 8, steer)
            struct.pack_into("<i", inp, 20, 1)
            call(dll, EXEC, inp)
            if step % 20 == 0 or step == args.frames - 1:
                state = (ctypes.c_ubyte * SIZE)()
                call(dll, GET_PLAY_STATE, state)
                race = (ctypes.c_ubyte * SIZE)()
                ok_race = call(dll, GET_2D_RACE, race)
                car = (ctypes.c_ubyte * SIZE)()
                effect = (ctypes.c_ubyte * SIZE)()
                ok_car = call(dll, GET_MY_CAR, car, effect)
                frame["samples"].append({
                    "step": step,
                    "state": bytes(state[:16]).hex(),
                    "race_ok": int(ok_race),
                    "race": bytes(race[:64]).hex(),
                    "car_ok": int(ok_car),
                    "car": bytes(car[:96]).hex(),
                })
        result["traces"].append(frame)

    call(dll, END)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf8") as handle:
        json.dump(result, handle, indent=1)
    for trace in result["traces"]:
        print("input", trace["input"])
        for sample in trace["samples"][:4]:
            print("  step %3d state=%s race=%s car=%s" %
                  (sample["step"], sample["state"],
                   sample["race"][:40], sample["car"][:40]))


if __name__ == "__main__":
    main()
