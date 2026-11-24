# P4 — Enma contract and vehicle dynamics

## Evidence

The dump ships `Wg6Enma_Release_IDL0.dll` (2,757,120 bytes, PE32+). It exports
172 MSVC-mangled C++ symbols with full parameter types. `tools/recon/enma_api.py`
reads the PE export table, calls every `GetE*Name` helper and recovers all 32
`SetDefault` struct layouts by poisoning buffers with three patterns. Raw output
is in gitignored `docs/recon/enma_api.json`.

Useful recovered API:

- `yt::CSeq::Init(SConfigPlay const&)`, `Exec(CGameInput const*)`, `End()`
- `GetPlayState`, `Get2DInfo*`, `GetInfoMyCarDisp`, `GetInfoLine*`
- `CGameInput::{getAccel,getBrake,getSteer,getGear,isIntrusion,isViewChange}`
- 16 enums, including 147 `ECarType`, 304 `EStage`, 208 `ECharacter`, 149
  `EAreaId`/`EJctBlockId`, 75 `ERamp` names.

`tools/recon/enma_sim.py` probes getters with single-offset writes:

| Field | Byte offset in `CGameInput` |
| --- | --- |
| accel | `0x00` (float) |
| brake | `0x04` (float) |
| steer | `0x08` (float) |
| gear | `0x14` (int) |

Ghidra decompilation of `FUN_1407a9c80` (`RacelibEnma.cpp`, in gitignored
`docs/recon/ghidra_init/enma_build_config.c`) gives the `SConfigPlay` offsets:
`eMode` `0x070`, `RaceField.eStage` `0x450`, `eStartAreaId` `0x454`,
`fStartAZ` `0x458`, `fGoalOdo` `0x45c`. `r6_enma.h` records this contract.

`yt::CSeq::Init()` called from a standalone process faults on a null host
pointer even after `ForEnmaReleaseBuild()` and with a valid stage/car; the DLL
needs state owned by `wmn6r.exe`. It cannot be used as an Android physics
backend. The model below is therefore an original implementation, not a lifted
copy of Enma.

## Car data actually used

`CarDataList` in `data/car/specification/<model>_Specification.lua` supplies
`Horsepower1st`, `EngineDisplacement`, `DriveSystem`, `MissionNumber`,
`TireOutsideFront/Rear`. `TireOutside` is the outer diameter in decimetres, so
wheel radius is `TireOutside / 20` metres. `GetTirePos(<car>, 0..3)` from the
position context returns the four contact points in decimetres: for
`CRC_928GT_Masaki` they are `x = ±7.73/7.80`, `z = +12.40/-12.68`, giving a
2.508 m wheelbase and 1.546 m track.

Mass is not present in `CarDataList`. `r6_vehicle_config_from_lua` uses the
explicit approximation `900 + 1.2 * horsepower` kg (1,296 kg for the 330 PS
928GT). Callers may replace it.

## Model

`engine/src/physics/vehicle.c` is freestanding C11: no CRT, no files, no
WinAPI, no libm. It provides:

- substepped semi-implicit integration (at most 16 steps, ~120 Hz);
- torque curve derived from peak power, with a 1.15 torque-peak factor and a
  low-rpm floor;
- gear ratios, final drive, efficiency, automatic up/downshift at 94% of the
  rpm limit and 1.8× idle;
- longitudinal force from drive torque, wheel braking, quadratic drag and
  rolling resistance, capped by tire friction;
- linear bicycle-model lateral dynamics with per-axle grip limits and a
  speed-sensitive steering reduction;
- local sin/cos and sqrt implementations (Taylor series and Newton), so no
  `libm` dependency is introduced;
- automatic reset to a finite state if any variable diverges.

Public API is in `engine/include/r6/r6_physics.h`; the Enma byte contract is in
`r6_enma.h`. JNI exposes `Vehicle` creation from the loaded Lua context,
stepping and state reads through `com.wmmt.re6rr.Re6Engine`.

## Validation

`python tools/engine/test_physics.py`:

- idle stays at zero position and speed;
- negative and NaN `dt` rejected;
- 8 s full throttle reaches 36.5 m/s in gear 3 with the default config;
- 2 s braking drops 36.5 → 15.6 m/s;
- steering produces yaw and yaw rate;
- 600 mixed throttle/brake/steer frames remain finite;
- real 928GT context yields 242,715 W, 2.508 m wheelbase, 1.546 m track,
  0.314 m wheel radius, 5 gears, and accelerates to 37.0 m/s in 8 s.

Full engine suite (`build_host.py --test`, `test_engine.py --corpus`,
`test_engine.py --skip-lua --limit 10000`) still passes.

## Gaps

- No collision, road surface, bank, slope, aero parts or ghost/phantom logic.
- Dynamics are calibrated to plausible arcade behaviour, not to Enma traces:
  the DLL cannot be driven standalone here.
- Android NDK/SDK still absent, so the JNI/CMake path remains uncompiled.
