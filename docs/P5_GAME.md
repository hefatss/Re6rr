# P5 — Game flow and SConfigPlay bridge

`engine/src/game/game.c` is a freestanding state machine over the game phases
that must happen before a race can run. It uses no CRT, files, WinAPI or
allocation; the host owns the storage returned by `r6_game_size()`.

## Phases

    select car -> select course -> race -> result -> reset -> select car

- `r6_game_init()` starts in `R6_GAME_SELECT_CAR` with default config
  (battle, stage 3, Hakone, one lap, 3 s countdown).
- `r6_game_select_car()` records the car index. Negative indices give
  `R6_ERR_ARG`; calls in the wrong phase give `R6_ERR_STATE`.
- `r6_game_select_course()` records course, area and stage and advances to
  `R6_GAME_SELECT_COURSE`.
- `r6_game_start()` advances to `R6_GAME_RACE`.
- `r6_game_step()` moves to `R6_GAME_RESULT` when a race state reports GOAL,
  TIME_UP, RETIRE or WRONG_WAY. Non-terminal outcomes keep the race phase.
- `r6_game_reset()` returns to car selection.

## Enma byte contract

Two layouts exist. `Wg6Enma_Release_IDL0.dll!SConfigPlay::SetDefault` poisons
only the first 1,124 bytes (`0x464`) of `SConfigPlay`. `FUN_1407a9c80` then
copies `SConfigPlay` (`param_2`) into a compact 0x464-byte CSeq scratch struct.
The older 0x070/0x450/0x454/0x458/0x45c values are offsets in that scratch
copy, not in `SConfigPlay`. Named log lines in `FUN_1407a9c80` fix these
`SConfigPlay` offsets:

| Offset | Type | Field |
| --- | --- | --- |
| `0x008` | int32 | `OperationVer.eJCT` (derived from source `param_2 + 8`) |
| `0x060` | int32 | `nRandomSeed` |
| `0x068` | int64 | `nSystemSec` (offset recorded, not serialized) |
| `0x098` | int32 | `eMode` (`EGameMode`) |
| `0x0b0` | int32 | `Story.eSeries` (via `FUN_1407b1cb0`) |
| `0x0b8` | int32 | `Story.nLap` |
| `0x0c4` | int32 | `Story.nCharacterNum` |
| `0x164` | int32 | `Battle.eRamp` |
| `0x168` | float | `Battle.fRunDist` |
| `0x178` | int32 | `Battle.nRivalNum` |
| `0x25c` | int32 | `Target.eStage` |
| `0x260` | uint8 | `Target.bIsTutorial` |
| `0x620` | uint8 | `Sampling.bEnable` |
| `0x630` | int32 | `RaceField.eStage` |
| `0x634` | int32 | `RaceField.eStartAreaId` |
| `0x638` | float | `RaceField.fStartAZ` |
| `0x63c` | float | `RaceField.fGoalOdo` |

The largest read is `param_2 + 0x640`, so `R6_ENMA_CFG_SIZE` is 1,604 bytes
(`0x644`); `R6_ENMA_CFG_SETDEFAULT_SIZE` keeps the 1,124-byte poisoned prefix.
`r6_game_write_config()` writes the 16 named scalar fields above; all other
bytes in the caller buffer are left as-is. `r6_game_read_config()` reads them
back. Time limit, countdown, car index, course enum and the 8-byte system
seconds have no recovered `SConfigPlay` offsets and remain native-only.
Buffers shorter than `R6_ENMA_CFG_SIZE` give `R6_ERR_BUFFER`.

## JNI

`Re6Engine.Game` exposes `create`, `phase`, `selectCar`, `selectCourse`,
`start`, `step(outcome, elapsed, dt)`, `reset`, `writeConfig` and `readConfig`.
The Java side owns the native handle and closes it in `AutoCloseable.close()`.

## Validation

`python tools/engine/test_game.py` checks:

- phase transitions, including rejected transitions in the wrong phase;
- GOAL moves a running race to result phase;
- config bytes land at all 16 recovered `SConfigPlay` offsets;
- a 1,603-byte buffer is rejected;
- config changes round-trip through write/read, while non-serialized fields
  survive in the native game object.

## Gaps

- `nSystemSec`, time limit, countdown, car index and course enum still have no
  recovered `SConfigPlay` offsets.
- Shipped rival AI behaviour, explicit goal/checkpoint-order tables and story
  unlock rules are not recovered; the core uses derived course flags and
  deterministic follow-course rivals. Shipped episode dialogue and timing are
  in the separate `.r6story` catalog documented in `docs/P5_STORY.md`.
- No Android NDK/SDK here, so the JNI/CMake path is still compile-checked only.
