/* Packed car catalog built from the shipped specification scripts. */
#ifndef R6_CAR_H
#define R6_CAR_H

#include <stddef.h>
#include <stdint.h>

#include "r6/r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_CAR_MODEL_SIZE 24
#define R6_CAR_NAME_SIZE 64
#define R6_CAR_MAKER_SIZE 24
#define R6_CAR_RECORD_SIZE 144
#define R6_CAR_RECORD_SIZE_V3 148
#define R6_CAR_RECORD_SIZE_V4 444
#define R6_CAR_ENGINE_SOUND_OFFSET 144
#define R6_CAR_NAME_JP_OFFSET 148
#define R6_CAR_CAR_NAME_OFFSET 212
#define R6_CAR_GLADE_OFFSET 236
#define R6_CAR_YEAR_OFFSET 284
#define R6_CAR_NAME_JP_SIZE 64
#define R6_CAR_CAR_NAME_SIZE 24
#define R6_CAR_GLADE_SIZE 48
#define R6_CAR_YEAR_SIZE 160
#define R6_CAR_MAP_SIZE 48
#define R6_CAR_HEADER_SIZE 24

enum r6_car_flags {
    R6_CAR_DRESS_UP = 1,
    R6_CAR_CUSTOM_COLOR = 2,
    R6_CAR_SUPERCHARGER = 4
};

typedef struct r6_car_map {
    char character[R6_CAR_MODEL_SIZE];
    char model[R6_CAR_MODEL_SIZE];
} r6_car_map;

typedef struct r6_car_info {
    char model[R6_CAR_MODEL_SIZE];
    char name[R6_CAR_NAME_SIZE];
    char maker[R6_CAR_MAKER_SIZE];
    uint16_t model_id;
    uint16_t visual_model_id;
    uint16_t horsepower;
    uint16_t engine_cc;
    uint8_t drive;
    uint8_t mission;
    uint8_t flags;
    uint8_t maker_id_low;
    float tire_front;
    float tire_rear;
    float tire_width_front;
    float tire_width_rear;
    uint32_t maker_id;
} r6_car_info;

/* Packed layout: 8-byte magic "R6CAR\0\1\0", u32 version, u32 car count,
 * u32 record size, u32 mapping count, then count records and mapping_count
 * 48-byte CRC_* -> PLC_* pairs. Versions 1/2 use 144-byte records, version 3
 * uses 148-byte records with EngineSound at +144 and a reserved u16, and
 * version 4 adds four cp932 text fields at +148. Version 1 has no mappings and
 * requires a zero mapping count. On R6_ERR_BUFFER, *count holds the required
 * car capacity. */
R6_API int r6_car_catalog_parse(const void *data, size_t size,
                                r6_car_info *cars, size_t capacity,
                                size_t *count);
R6_API int r6_car_catalog_find_model(const r6_car_info *cars, size_t count,
                                     const char *model);
R6_API int r6_car_catalog_find_id(const r6_car_info *cars, size_t count,
                                  uint16_t model_id);
/* Verbatim EngineSound from a version-3 blob (0..31 in the shipped catalog).
 * Older blobs have no field and return R6_ERR_FORMAT. */
R6_API int r6_car_catalog_engine_sound(const void *data, size_t size,
                                       size_t index, uint16_t *out);

/* Field selectors for r6_car_catalog_text_field(). */
enum r6_car_text_field {
    R6_CAR_TEXT_NAME = 0,
    R6_CAR_TEXT_MAKER = 1,
    R6_CAR_TEXT_NAME_JP = 2,
    R6_CAR_TEXT_CAR_NAME = 3,
    R6_CAR_TEXT_GLADE = 4,
    R6_CAR_TEXT_YEAR = 5
};

/* Copy one NUL-terminated cp932 field into caller storage. Fields 2..5 need a
 * version-4 blob; older blobs return R6_ERR_FORMAT. */
R6_API int r6_car_catalog_text_field(const void *data, size_t size,
                                     size_t index, uint32_t field,
                                     char *out, size_t capacity);

/* Raw-blob lookups into the mapping section; no unpacked storage needed. */
R6_API int r6_car_catalog_character_count(const void *data, size_t size);
R6_API int r6_car_catalog_find_character(const void *data, size_t size,
                                         const char *character);

#ifdef __cplusplus
}
#endif

#endif
