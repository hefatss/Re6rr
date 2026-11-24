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

SetDefault buffer poisoning from `Wg6Enma_Release_IDL0.dll` writes up to 1,124
bytes (`0x464`) of `SConfigPlay`. `R6_ENMA_CFG_SIZE` records that size. The
Ghidra decompile of `FUN_1407a9c80` fixed these field offsets:

| Offset | Type | Field |
| --- | --- | --- |
| `0x070` | int32 | `eMode` (`EGameMode`) |
| `0x450` | int32 | `RaceField.eStage` |
| `0x454` | int32 | `RaceField.eStartAreaId` |
| `0x458` | float | `fStartAZ` |
| `0x45c` | float | `fGoalOdo` |

`r6_game_write_config()` writes only those five fields; all other bytes in
the caller buffer are left as-is. `r6_game_read_config()` reads them back into
the game config without touching time limit, countdown, laps, car index or
rival count, since their offsets are not recovered. Buffers shorter than
`R6_ENMA_CFG_SIZE` give `R6_ERR_BUFFER`.

## JNI

`Re6Engine.Game` exposes `create`, `phase`, `selectCar`, `selectCourse`,
`start`, `step(outcome, elapsed, dt)`, `reset`, `writeConfig` and `readConfig`.
The Java side owns the native handle and closes it in `AutoCloseable.close()`.

## Validation

`python tools/engine/test_game.py` checks:

- phase transitions, including rejected transitions in the wrong phase;
- GOAL moves a running race to result phase;
- config bytes land at the exact recovered offsets;
- a 1,123-byte buffer is rejected;
- config changes round-trip through write/read, while non-serialized fields
  survive in the native game object.

## Gaps

- Only five `SConfigPlay` fields have known offsets; the remaining config is
  native-only and never enters the Enma struct.
- No menu rendering, input mapping, car catalog, rival AI or story progression.
- No Android NDK/SDK here, so the JNI/CMake path is still compile-checked only.
