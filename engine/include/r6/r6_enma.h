/* Contract recovered from Wg6Enma_Release_IDL0.dll and the exe bridge
 * FUN_1407a9c80 (RacelibEnma.cpp). These are byte offsets into the two
 * structs exchanged with yt::CSeq; the freestanding core does not depend on
 * them, but host tooling and the Android bridge can use them to interoperate.
 */
#ifndef R6_ENMA_H
#define R6_ENMA_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* CGameInput: read offsets from ?getAccel/getBrake/getSteer/getGear@CGameInput. */
#define R6_ENMA_INPUT_ACCEL     0x00
#define R6_ENMA_INPUT_BRAKE     0x04
#define R6_ENMA_INPUT_STEER     0x08
#define R6_ENMA_INPUT_GEAR      0x14

/* SConfigPlay source layout. FUN_1407a9c80 copies param_2 into a compact
 * 0x464-byte CSeq scratch struct; the old 0x070/0x450/... values are offsets
 * in that scratch copy, not in SConfigPlay. The constants below are the
 * original param_2 offsets read by the named log lines. */
#define R6_ENMA_CFG_OPERATION_JCT  0x008
#define R6_ENMA_CFG_RANDOM_SEED    0x060
#define R6_ENMA_CFG_SYSTEM_SEC     0x068
#define R6_ENMA_CFG_MODE           0x098
#define R6_ENMA_CFG_STORY_SERIES   0x0b0
#define R6_ENMA_CFG_STORY_LAPS     0x0b8
#define R6_ENMA_CFG_STORY_CHARS    0x0c4
#define R6_ENMA_CFG_BATTLE_RAMP    0x164
#define R6_ENMA_CFG_BATTLE_RUN_DIST 0x168
#define R6_ENMA_CFG_BATTLE_RIVALS  0x178
#define R6_ENMA_CFG_TARGET_STAGE   0x25c
#define R6_ENMA_CFG_TARGET_TUTORIAL 0x260
#define R6_ENMA_CFG_SAMPLING       0x620
#define R6_ENMA_CFG_STAGE          0x630
#define R6_ENMA_CFG_AREA           0x634
#define R6_ENMA_CFG_START_AZ       0x638
#define R6_ENMA_CFG_GOAL_ODO       0x63c

/* Compact CSeq scratch copy, kept only for comparison with older reports. */
#define R6_ENMA_CSEQ_MODE          0x070
#define R6_ENMA_CSEQ_STAGE         0x450
#define R6_ENMA_CSEQ_AREA          0x454
#define R6_ENMA_CSEQ_START_AZ      0x458
#define R6_ENMA_CSEQ_GOAL_ODO      0x45c

/* EPlayState, recovered with ?GetEPlayStateName@@YAPEBDW4EPlayState@@@Z. */
enum r6_enma_play_state {
    R6_ENMA_PLAY_NONE = 0,
    R6_ENMA_PLAY_COUNTDOWN = 1,
    R6_ENMA_PLAY_RUN = 2,
    R6_ENMA_PLAY_RETIRE = 3,
    R6_ENMA_PLAY_SLOWDOWN = 4,
    R6_ENMA_PLAY_STOP_WAIT = 5,
    R6_ENMA_PLAY_TIME_UP = 6,
    R6_ENMA_PLAY_GOAL_WAIT = 7,
    R6_ENMA_PLAY_GOAL = 8,
    R6_ENMA_PLAY_DEFEAT = 9,
    R6_ENMA_PLAY_SUSPEND = 10
};

/* EGameMode, recovered with ?GetEGameModeName@@YAPEBDW4EGameMode@@@Z. */
enum r6_enma_game_mode {
    R6_ENMA_MODE_NONE = 0,
    R6_ENMA_MODE_MAP_RUNNER = 1,
    R6_ENMA_MODE_ENDING = 2,
    R6_ENMA_MODE_STORY = 3,
    R6_ENMA_MODE_BATTLE = 4,
    R6_ENMA_MODE_TIME_ATTACK = 5,
    R6_ENMA_MODE_TARGET = 6,
    R6_ENMA_MODE_PHANTOM = 7,
    R6_ENMA_MODE_EVENT = 8
};

enum r6_enma_transmission {
    R6_ENMA_AT = 0,
    R6_ENMA_MT = 1
};

/* Selected values from GetECourseName / GetEStageName / GetESurfaceName. */
enum r6_enma_course {
    R6_ENMA_COURSE_NONE = 0,
    R6_ENMA_COURSE_HAKONE = 1,
    R6_ENMA_COURSE_METRO = 2,
    R6_ENMA_COURSE_OSAKA = 3,
    R6_ENMA_COURSE_NAGOYA = 4
};

enum r6_enma_surface {
    R6_ENMA_SURFACE_NONE = 0,
    R6_ENMA_SURFACE_GRASS = 1,
    R6_ENMA_SURFACE_GRAVEL = 2
};

#ifdef __cplusplus
}
#endif

#endif
