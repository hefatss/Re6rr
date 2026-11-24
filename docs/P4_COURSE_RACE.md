# P4 — Course projection and race rules

## Contract

`yt::CSeq` in `Wg6Enma_Release_IDL0.dll` owns the race state and exposes
`EPlayState` (`NONE`, `CountDown`, `Run`, `Retire`, `SlowDown`, `StopWait`,
`TimeUp`, `GoalWait`, `Goal`, `Defeat`, `Suspend`) through `GetPlayState`.
The values are recovered from the DLL's `GetEPlayStateName` export and recorded
in `engine/include/r6/r6_enma.h`. `SConfigPlay.fGoalOdo` defaults to `1e8`; the
named log line in `FUN_1407a9c80` places the field at byte `0x63c` of the
`SConfigPlay` source struct (the compact CSeq copy uses `0x45c`).

The shipped DLL still cannot be initialised without the executable's host
state, so the freestanding core implements its own deterministic race rules
using the same enum values and configuration names.

## Course module

`engine/include/r6/r6_course.h` describes a road as an ordered polyline of
`r6_course_vertex` values in metres:

| Field | Meaning |
| --- | --- |
| `x, y, z` | ground position; `y` is height |
| `half_width` | drivable half-width |
| `surface` | `0` road, `1` grass, `2` gravel |
| `flags` | `CHECKPOINT`, `START`, `GOAL`, `JUNCTION` |

`engine/src/physics/course.c` is stateless: the host keeps the vertices, the
core computes arc length on demand. `r6_course_project()` returns the nearest
segment's arc length, signed lateral offset, tangent, height, width, surface
and flags. `r6_course_at()` interpolates the centreline at a given arc length.
There is no CRT, `libm` or allocation, so the same code runs in the host DLL
and on Android.

## Shipped course data

`tools/engine/course_descriptor.py` turns the dump's own course data into a
packed descriptor; no road mesh is needed for this first port:

- `data/course/path/<AREA>/*.bin` — headerless float32 `(x, y, z)` triples in
  source units. `NavimapParam.lua` states `1m=10`, so values are divided by 10.
- `data/course/debug/course_viewer_multi_path.lua` — `PathTable` supplies the
  exact route order, `Loop` flag and camera direction for each `MenuText`.
- `data/course/section/SECT_A_<AREA>.lua` — `SECT_POLYGON` sections. Each
  `GEO` edge is a start point plus a delta; the tool builds polygons and tags
  each path sample with the containing `SECT_ID`. Fallback comes from the
  `SectNNN` part of the file name.

`python tools/engine/course_descriptor.py --list-routes` prints all routes.
Example output for Fukuoka:

    FUKUOKA: 2816 vertices, 56344 bytes, closed=1, sections [101, 102, 103, 104]

The six pieces are `KKS_Sect1`, `KKS_Sect2_In`, `KKS_Sect3_In`, `KKS_Sect4`,
`KKS_Sect3_Out` and `KKS_Sect2_Out`, with one `START`, one `GOAL` and five
`CHECKPOINT` flags. Hakone yields 2,142 vertices and Nagoya 759.

Descriptor layout (little endian):

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | magic `R6CRS\0\1\0` |
| 8 | 4 | version `1` |
| 12 | 4 | flags; bit 0 = closed |
| 16 | 4 | vertex count |
| 20 | 4 | reserved |
| 24 | 20 × count | `x, y, z, half_width` floats, then `surface` u8, `flags` u8, `reserved` u16 |

`r6_course_descriptor_parse()` validates the whole blob and fills a caller
array. `R6_ERR_BUFFER` reports the required vertex capacity, matching the
gzip-inflate convention.

### Surface and width from stage models

`tools/engine/course_surface.py` supplies the two fields the path bins do not
carry. Ghidra decompile of `FUN_140127e10` (`course_load_manager.cpp`) confirms
the loader walks area → stage → section, reading `StageNum` and `SectionNum`
from Lua with section IDs starting at 101. Matching that order:

- `data/course/stage/A_<AREA>_<TIME>_NML/<AREA>/model/LOADLIST_*.lua` pairs
  `ROAD_ADDR {offset,size,...}` with `ROAD_NAME {"...",...}` per section.
- The `BIN` entry resolves to `model/bin/*_SECT<id>.bin`, a gzip container whose
  inflated payload holds NDWD streams at those offsets.
- Course NDWD streams use 28-byte vertices:
  `f32 y, f32 z, f32 u, f32 v, u32 color, u32 normal, f32 x`. The same 10-unit
  scale as the path bins applies.
- Suffix names classify surface: `broad*`, `nroad*`, `road_*`, `route*`, `conc*`
  → road (0); `tpKusa*`, `green*`, `bush*`, `grass*` → grass (1);
  `gravel*`, `grail*` → gravel (2). `ONRD` is a decal layer and is skipped.
- Vertices are projected onto the shipped centreline with a 20 m spatial hash.
  Per five-sample window, the vertex majority sets the surface and the dominant
  lateral-distance bin inside 1–10 m sets the half-width. `--half-width` is only
  a fallback when no model vertices land near a window.

Measured results: Fukuoka 2,816 road vertices, half-width 2.0–10.0 m (mean
6.71 m); Turnpike 1,210 vertices, 195 grass and 10 gravel samples, half-width
mean 6.04 m. `course_descriptor.py --no-surface` disables extraction.

## Race module

`engine/include/r6/r6_race.h` and `engine/src/physics/race.c` implement:

- countdown in seconds, then `Run`;
- progress from course arc length (`s`), with forward wrap incrementing the
  lap and backward wrap decrementing it;
- elapsed, lap, last lap and best lap timing;
- goal by `goal_odo` or lap count, using `EPlayState.Goal`;
- time limit using `EPlayState.TimeUp`;
- sustained reverse travel over `wrong_way_limit` seconds using
  `EPlayState.Retire` and outcome `R6_RACE_WRONG_WAY`;
- off-road detection when `|lateral| > half_width * offroad_factor`, with the
  vertex surface carried into the state; callers feed that surface back through
  `Vehicle.setSurface()` so grip and rolling drag follow the road;
- finite-state guard that resets the race on divergence.
- rival tracking: nearest gap, side offset, place, and contact events using
  approximate car footprints (4.5 m × 1.9 m).

When no course vertices are supplied, progress falls back to the vehicle's
odometer, matching the `fGoalOdo` field in `SConfigPlay`.

`r6_race_config_default()` uses mode `Battle`, stage `Series01`, course
`Hakone`, a 3-second countdown, one lap, a 2-second wrong-way limit and a
`1e8` goal distance.

### Rival rules

`r6_race_set_rivals()` accepts up to eight `r6_rival_state` records: world
position, yaw, speed, optional course arc length, lateral offset and an ID.
Each step transforms rival offsets into the player's course-tangent frame, so
no trig is needed when a course is present. `rival_gap` is the nearest rival
ahead, `rival_position` is `1 +` the number of rivals ahead, and `rival_side`
is the lateral offset to that rival.

Overlap of the two approximate car footprints increments `collision_count`,
sets `EPlayState.SlowDown` and outcome `R6_RACE_COLLISION` for one frame. A
0.5-second cooldown prevents repeated counts while cars stay overlapped; the
next step returns to `Run`. Collisions are events, not a terminal race state.

## JNI

`com.wmmt.re6rr.Re6Engine` now exposes `Race`:

- `Re6Engine.createRace()` / `createRace(...)`;
- `Race.step(float[] vertices, boolean closed, float[] vehicle, float dt)`;
- `Race.step(byte[] descriptor, float[] vehicle, float dt)` — parse a packed
  `.r6course` blob natively and take the closed flag from its header;
- `Race.setRivals(float[] rivals)` — each rival is eight floats
  `x y z yaw speed s lateral id`, at most eight rivals;
- `Race.state()` — 23 floats: play state, outcome, elapsed, countdown, lap,
  lap time, last lap, best lap, `s`, progress, odo, lateral, height, half width,
  speed, off-road time, wrong-way time, surface, off-road flag, checkpoint
  flags, rival gap, rival side, rival place and collision count.

Each course vertex passed over JNI is eight floats: `x y z halfWidth surface
flags reserved pad`. The JNI layer converts that array and the 15-float
`Vehicle.state()` result into the C structs; the core never sees JNI types.

## Validation

`python tools/engine/test_race.py` checks:

- 100 m straight length, projection at `(25, 3)` → `s=25`, `lateral=3`,
  tangent `+x`, and `r6_course_at(25) = (25, 0, 0)`;
- 400 m closed square, forward wrap from `s=390` to `s=5` → lap 2;
- Fukuoka descriptor parses to 2,816 closed vertices, first sample
  `(3259.54, -962.88)` m and sample 50 projects to `s=512.83` m;
- Turnpike descriptor carries 195 grass and 10 gravel samples, matching the
  Python surface counts through the C parser;
- countdown holds progress at zero, then goal at `progress >= goal_odo`;
- off-road detection on the gravel segment;
- sustained reverse travel → `Retire` / `R6_RACE_WRONG_WAY`;
- two rivals produce gap 10 m and place 2; contact produces one collision,
  `SlowDown`, then a return to `Run`; nine rivals are rejected;
- negative `dt` and null vehicle rejected;
- 180 frames of the real vehicle model driving the race stay finite and
  advance progress.

Result: all course/race checks passed. Full host suite, engine parity tests,
physics tests and JNI/Java syntax checks still pass.

## Gaps

- Path bins have no width, surface or checkpoint/goal-order fields. Width and
  surface are estimated from `ROAD` mesh names and vertex distribution;
  checkpoint flags follow piece boundaries.
- Stage models contribute only surface class and half-width. Triangle strips,
  `ONRD` markings, `LONG`/`NEAR` scenery and clip tables are not reconstructed.
- Rival collision is a state event only: no rival impulse, damage or speed
  penalty is applied yet. Road-wall correction is separate, in
  `r6_vehicle_clamp_to_course()`.
- No surface-dependent grip feedback, road bank or slope, weather, aero parts
  or ghost/phantom data.
- Race rules are calibrated to the recovered enum/state names, not to Enma
  traces.
