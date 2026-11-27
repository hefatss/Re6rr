# P5 — Story catalog

`tools/engine/story_catalog.py` derives one packed `.r6story` blob from local
scene data. No game data is committed; the tool reads the player's own dump.

    python tools/engine/story_catalog.py --dump D:\Games\W6W-05 \
        --out build/tmp/story.r6story --report build/tmp/story.json

## Evidence

- `data_jp/scene/ESeries_*` holds 121 numbered mission directories with phases
  `FrontEvent`, `Race` and `RearEvent`, plus `ESeries_Ending`. 21 missions have
  an A/B pair.
- `docs/recon/name_tables.json` string table `0x1e39220` holds 993 executable
  names including `ESeries_NONE` and 122 `ESeries_*` enum strings. Directory
  names `ESeries_<nnn>` map to that table. `ESeries_<nnn>A` dirs share the base
  enum because the enum has no `A` suffix; `B` dirs have their own enum.
- `data_jp/scene/ESeries_*/**/*.xmlt` has 265 `Event.xmlt` and 326
  `Message.xmlt` files (591 total, UTF-8). `Message.xmlt` holds ordered `<MES>`
  text. `Event.xmlt` binds `MESSAGE`, `LETTERING`, `CUT_IN_HIT_*` and
  `CUT_IN_RANGE_*` seeds to frames, actor slots, ranges and cut-in paths.
- `data_jp/scene/ESeries_*/**/Environment.Lua` carries raw `ACTOR_0..3`,
  `STAGE`, `STAGE_ROOT`, `STAGE_DAY` and `CAM_ID` numeric globals. The value is
  packed as-is; no shipped file maps those numbers to `CRC_*`/`PLC_*` cars or
  `EStage_*` courses.
- `data_jp/msgdb/msgdb.lua` contains 647 `drive_story_*` runtime strings. The
  shipped file is English-patched for some keys; the authoring
  `data/msgdb/BN-W5_メッセージデータベース_VBA.xlsm` keeps JP/US/CNL columns but
  is not loaded at runtime.

## Packed layout

Little endian. Header is 32 bytes:

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | magic `R6STO\0\1\0` |
| 8 | 4 | version `1` |
| 12 | 4 | episode count |
| 16 | 4 | message count |
| 20 | 4 | event count |
| 24 | 4 | story-key count |
| 28 | 4 | shared string byte count |

Sections follow in that order. All offsets point into the final string byte
section and every string is NUL-terminated UTF-8.

| Section | Record | Contents |
| --- | --- | --- |
| episode | 64 B | `enum_index`, `name[32]`, phase/branch flags, message and event counts, 4 raw actor numbers, raw stage/root/day/camera numbers |
| message | 16 B | `text_offset`, episode, local ID, text length, phase |
| event | 32 B | episode, phase, kind, start/end frames, range, `mes_id`, actor slot, position, cut-in/lettering text offset and length |
| story key | 16 B | ID offset, value offset, ID length, value length |
| strings | variable | NUL-terminated UTF-8 blob |

Episode flags: front 1, race 2, rear 4, branch B 8, ending 16, environment 32.
Event kinds: message 1, lettering 2, cut-in hit 3, cut-in range 4.
`ESeries_Ending` uses enum index 0 because no `ESeries_*` enum string exists for
it.

## C API

`engine/include/r6/r6_story.h` and `engine/src/game/story.c` validate magic,
version, counts and exact size, then return typed section views. Record
accessors copy into caller storage; string accessors copy NUL-terminated text
into caller buffers and reject too-small buffers. Lookups exist for episode
name and `drive_story_*` key. `r6_story_catalog_summary()` counts the stored
phase, kind and flag fields directly; it does not infer dialogue, unlock or
mission-order semantics.

## JNI

`Re6Engine.StoryCatalog` wraps the blob on Android. `count(section)` uses
episode/message/event/key/string order. `episode()` and `episodeName()` expose
the episode tree; `message()`, `event()` and `key()` expose fixed records.
`messageText()`, `eventText()`, `keyId()` and `keyValue()` decode UTF-8 text
from the shared string section. `findEpisode()` and `findKey()` return `-1` for
unknown names. `summary()` returns message phases, event phases, event kinds,
branch-B/ending/environment counts, enum-index-zero rows and empty key values
as 15 plain ints. Java owns the byte array; native code only validates and
copies.

## Validation

`python tools/engine/test_story_catalog.py` checks section counts, ctypes record
sizes, sampled records, shared-string reads, lookups, all 15 summary fields and
malformed blobs. Result: 122 episodes, 3,309 messages, 3,484 events, 647 story
keys, 204,057 string bytes, 386,681 bytes total. Summary: message phases
236/3,005/68, event phases 342/3,074/68, event kinds 304/106/186/2,888,
branch B 21, ending 1, environment 59, enum-zero 22 and empty key values 149.

## Gaps

- No shipped mission-order, unlock, reward or condition table. Only the episode
  tree and its local dialogue/timing are authoritative. Native condition schema
  is recovered in `docs/recon/STORY_NATIVE.md`, but the per-episode instances
  are not in the dump.
- `ACTOR_*` and `STAGE` are plain `int32` scene values read and written verbatim
  by `EventScene2Analyzer.cpp` / `EventSceneEditor.cpp`; see
  `docs/recon/STORY_NATIVE.md`. Ghidra full analysis recovered the exact editor
  slots: stage/root/day come from struct offsets `0x10/0x14/0x18` and actors
  1..4 from `0x00/0x04/0x08/0x0c`, with native `GetStageId` / `GetActId_1..4`
  error labels. `FUN_1401e3640` copies the eight slots into scene struct offsets
  `0x08/0x0c/0x10/0x14/0x18/0x1c/0x20/0x24`. `FUN_1401fae70` then passes
  `stage - 1`, `stage_day` and each actor through
  `FUN_1401d1db0` / `FUN_1401d1d00` / `FUN_1401d1d20`, resolving to `EAreaId_*`,
  `Day_*`/`NIGHT`, and `getCarIdName` names. `tools/engine/scene_config.py`
  reproduces those lookups from the shipped binary's 254-car, 149-stage and
  5-day pointer tables; all 59 shipped episodes resolve. This proves scene
  actor-to-car *name* resolution, not rival instantiation or gameplay model
  assignment. Stage values occupy native `EStage` fields: the `CSeq::Init`
  builder copies three live-config offsets verbatim into `SConfigPlay`, logging
  them as `target, eStage: %d`, `phantom, eStage: %d`, and the
  `====== Phantom =======` section; the caller names live offset `0x630`
  `config_play->RaceField.eStage`. All 26 shipped stage values are valid Enma
  `EStage` indices. One scene-to-config bridge is now proven: `FUN_1401eaab0`
  copies scene struct `+0x24` (`CAMID`) into the embedded camera config at
  scene base `+0x740+0x70`; `FUN_1401f1f20` uses that value to select the
  `CamData.EES` slot at base `+0x2d78 + camid*0x1b0` and copies it to the
  loader at `+0x48`, while `FUN_1401e1ff0` uses it to index 255-entry camera
  arrays. `tools/engine/scene_bridge.py` models the copy and lookup; all 59
  shipped episodes use camid `0..2`. No write from stage/root/day/actor scene
  fields into live-config `0x630` was found, so that propagation stays
  unproven. `CAR_ID` is a cut-in actor slot, not a `CRC_*` ID.
- 3.10 GB of `.EES` cutscene camera/model data is not parsed.
- gzip/NTWD cut-in textures are not decoded; only their paths are catalogued.
- `LETTERING` points at `data_jp/flash/DRIVE/Race/EVENT/` files whose text is
  not in `msgdb.lua`.
- Unlock predicates, rival assignment and stage mapping stay explicit native
  decisions until recovered from the executable, not invented here.
