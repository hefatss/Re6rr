/* Freestanding game flow and SConfigPlay bridge.
 *
 * Phase transitions model the minimum sequence required to go from car select
 * to a race result. Serialization writes only fields whose byte offsets were
 * recovered from the shipped Enma DLL; unknown fields are left untouched.
 */
#ifndef R6_GAME_H
#define R6_GAME_H

#include <stddef.h>
#include <stdint.h>

#include "r6/r6.h"
#include "r6/r6_enma.h"
#include "r6/r6_race.h"

#ifdef __cplusplus
extern "C" {
#endif

/* SetDefault poisons only the first 0x464 bytes, but SConfigPlay also holds
 * the RaceField/Phantom fields up to 0x640 read by FUN_1407a9c80. */
#define R6_ENMA_CFG_SETDEFAULT_SIZE 1124u
#define R6_ENMA_CFG_SIZE 1604u

enum r6_game_phase {
    R6_GAME_TITLE = 0,
    R6_GAME_SELECT_CAR = 1,
    R6_GAME_SELECT_COURSE = 2,
    R6_GAME_RACE = 3,
    R6_GAME_RESULT = 4
};

typedef struct r6_game_config {
    int mode;         /* r6_enma_game_mode */
    int stage;        /* EStage */
    int area;         /* EAreaId */
    int course;       /* r6_enma_course */
    int car_index;
    int rival_count;
    float start_az;
    float goal_odo;
    float time_limit;
    float countdown;
    int laps;
    int series;
    int character_count;
    int battle_ramp;
    float battle_run_dist;
    int target_stage;
    int target_tutorial;
    int sampling;
    int random_seed;
    int operation_jct;
} r6_game_config;

typedef struct r6_game r6_game;

R6_API size_t r6_game_size(void);
R6_API void r6_game_config_default(r6_game_config *config);
R6_API r6_game *r6_game_init(void *storage, size_t size,
                             const r6_game_config *config);
R6_API int r6_game_get_config(const r6_game *game, r6_game_config *out);
R6_API int r6_game_set_config(r6_game *game, const r6_game_config *config);
R6_API int r6_game_phase(const r6_game *game);
R6_API int r6_game_select_car(r6_game *game, int index);
R6_API int r6_game_select_course(r6_game *game, int course, int area,
                                 int stage);
R6_API int r6_game_start(r6_game *game);
R6_API int r6_game_step(r6_game *game, float dt,
                        const r6_race_state *race_state);
R6_API int r6_game_reset(r6_game *game);

/* Enma byte contract. Buffer must be at least R6_ENMA_CFG_SIZE bytes. */
R6_API int r6_game_write_config(const r6_game *game, void *buffer,
                                size_t size);
R6_API int r6_game_read_config(r6_game *game, const void *buffer, size_t size);

/* Environment.Lua camid bridge: scene +0x24 -> SConfigPlay +0x70, then the
 * five camera containers at scene +0x2d78 with a 0x1b0 stride. */
enum {
    R6_SCENE_CAMID_OFFSET = 0x24,
    R6_SCENE_SIZE = 0x28,
    R6_SCENE_CONFIG_CAMID_OFFSET = 0x70,
    R6_SCENE_CONFIG_OFFSET = 0x740,
    R6_SCENE_CONTAINER_BASE = 0x2D78,
    R6_SCENE_CONTAINER_STRIDE = 0x1B0,
    R6_SCENE_CONTAINER_COUNT = 5,
    R6_SCENE_LOADER_CAMID = 0x48,
    R6_SCENE_RECORD_SIZE = 0x10
};

/* Copy the signed camid from a scene slot into a caller-owned config buffer. */
R6_API int r6_scene_write_camid(const void *scene, size_t scene_size,
                                void *config, size_t config_size,
                                int32_t *out);

/* 0x1401f1f20: camera container byte offset for a slot below five. */
R6_API int r6_scene_container_offset(uint32_t slot, size_t *out);

/* 0x1401e1ff0: first non-empty camera record covering frame, else -1.
 * Records are 0x10 bytes: type, start, end, exact, all signed i32, with a
 * negative end meaning no interval. */
R6_API int r6_scene_runtime_camera(const void *records, size_t size,
                                   int32_t frame);

/* EventScene2 container layout validated by FUN_1401cd0a0 / FUN_1401cd650. */
enum {
    R6_EES_KIND_CAM = 0,
    R6_EES_KIND_CAR = 1,
    R6_EES_ARRAY_CAMERA_INFO = 0,
    R6_EES_ARRAY_CAMERA_DATA = 1,
    R6_EES_ARRAY_CAR_DISP = 2,
    R6_EES_ARRAY_CAR_EFFECT = 3,
    R6_EES_ARRAY_CAR_INFO = 4,
    R6_EES_ARRAY_MAX = 3
};

typedef struct r6_ees_array_t {
    uint32_t name;
    uint32_t count;
    uint32_t stride;
    uint32_t offset;
    uint32_t size;
} r6_ees_array_t;

typedef struct r6_ees_header_t {
    uint32_t kind;
    uint32_t version;
    uint32_t file_size;
    uint32_t count;
    uint32_t effect_count;
    uint32_t header_size;
    uint32_t array_count;
    r6_ees_array_t arrays[R6_EES_ARRAY_MAX];
} r6_ees_header_t;

R6_API int r6_ees_parse(const void *data, size_t size, r6_ees_header_t *out);

/* FUN_1401e0330 names 31 fields in the 0x160-byte camera_data record. The
 * logger prints several f32 members with "%d"; the declared types below come
 * from the recovered struct, not the print format. */
enum {
    R6_EES_CAMERA_STRIDE = 0x160,
    R6_EES_CAMERA_FIELD_COUNT = 31
};

typedef struct r6_ees_camera_fields_t {
    int32_t m_CamType;
    int32_t m_StratFrame;
    float m_ActFrame;
    uint8_t m_WiatMode;
    float m_StratFieldAngle;
    float m_EndFieldAngle;
    int32_t m_FieldAngleCalcId;
    int32_t m_GlobalLookAt;
    int32_t m_LookAtId;
    float m_LookAtStartRenge;
    float m_LookAtStartCamRotX;
    float m_LookAtStartCamRotY;
    float m_LookAtStartCamRotZ;
    float m_LookAtEndRenge;
    float m_LookAtEndCamRotX;
    float m_LookAtEndCamRotY;
    float m_LookAtEndCamRotZ;
    int32_t m_TransCalcId;
    int32_t m_RotCalcId;
    float m_StratOpRotZ;
    float m_EndOpRotZ;
    int32_t m_OpRotZCalcId;
    float m_LookAtStartOfsetPosX;
    float m_LookAtStartOfsetPosY;
    float m_LookAtStartOfsetPosZ;
    float m_LookAtEndOfsetPosX;
    float m_LookAtEndOfsetPosY;
    float m_LookAtEndOfsetPosZ;
    int32_t m_OfsetCalcId;
    int32_t m_StartConnection;
    int32_t m_EndConnection;
} r6_ees_camera_fields_t;

/* Copy one record from caller-owned .EES bytes at `offset`. */
R6_API int r6_ees_camera_fields(const void *data, size_t size, uint32_t offset,
                                r6_ees_camera_fields_t *out);

/* FUN_1401c8f60: last non-empty 0x160 camera record covering `frame`, or -1.
 * exact=1 compares the start frame only; otherwise end=trunc(start+duration). */
R6_API int r6_ees_camera_at_frame(const void *data, size_t size,
                                  uint32_t offset, uint32_t count,
                                  int32_t frame);

/* FUN_1401ca060 keeps only camera records with type 0 or 2. */
R6_API int r6_ees_camera_accept_type(int32_t type);

/* car_info record (stride 0x8c): its int32 id, -1 as the native default. */
enum { R6_EES_CAR_INFO_STRIDE = 0x8C };

R6_API int r6_ees_car_info(const void *data, size_t size, uint32_t offset,
                           int32_t *out);

/* FUN_1401cc390 copies 40 fields from a 0xa0 car_effect record into the
 * 0xe0-byte runtime SInfoCarEffectCopy record. */
enum {
    R6_EES_CAR_EFFECT_STRIDE = 0xA0,
    R6_EES_CAR_EFFECT_COPY_SIZE = 0xE0,
    R6_EES_CAR_EFFECT_COPIES = 40
};

R6_API int r6_ees_car_effect_copy(const void *source, size_t size,
                                  void *out, size_t out_size);

/* One 0x180-byte car_disp record: id, flags, 16-f32 matrix and yaw. The yaw
 * unit count mirrors the native round(yaw * 65536 / 2pi) quantisation. */
enum {
    R6_EES_CAR_DISP_STRIDE = 0x180,
    R6_EES_CAR_DISP_MATRIX_OFFSET = 0x10,
    R6_EES_CAR_DISP_YAW_OFFSET = 0x150,
    R6_EES_CAR_DISP_MATRIX_FLOATS = 16
};

typedef struct r6_ees_car_disp_t {
    int32_t car_id;
    uint8_t flags;
    uint8_t reserved[11];
    float matrix[R6_EES_CAR_DISP_MATRIX_FLOATS];
    uint8_t reserved2[0x100];
    float yaw;
    int64_t yaw_units;
} r6_ees_car_disp_t;

R6_API int r6_ees_car_disp(const void *data, size_t size, uint32_t offset,
                           r6_ees_car_disp_t *out);

/* FUN_1401e3640 packs eight int32 environment slots into a 0x28 scene. */
typedef struct r6_scene_values_t {
    int32_t stage;
    int32_t stage_root;
    int32_t stage_day;
    int32_t cam_id;
    int32_t actors[4];
} r6_scene_values_t;

R6_API int r6_scene_pack(const r6_scene_values_t *values, void *out,
                         size_t size);

/* Packed native name tables (R6SCN) used by the scene debug logger. */
enum {
    R6_SCENE_CAR_NAMES = 0,
    R6_SCENE_STAGE_NAMES = 1,
    R6_SCENE_DAY_NAMES = 2,
    R6_SCENE_NAMES_KINDS = 3
};

typedef struct r6_scene_names_header {
    uint32_t counts[R6_SCENE_NAMES_KINDS];
    uint32_t strings_off;
    uint32_t strings_size;
} r6_scene_names_header;

R6_API int r6_scene_names_parse(const void *data, size_t size,
                                r6_scene_names_header *out);

/* Copy the resolved name into caller storage. Car ids -1 or out of range give
 * "PLC_NON"; stage and day ids outside the table report not found. */
R6_API int r6_scene_names_get(const void *data, size_t size, int kind,
                              int32_t value, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
