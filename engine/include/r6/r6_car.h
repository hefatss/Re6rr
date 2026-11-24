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
#define R6_CAR_HEADER_SIZE 24

enum r6_car_flags {
    R6_CAR_DRESS_UP = 1,
    R6_CAR_CUSTOM_COLOR = 2,
    R6_CAR_SUPERCHARGER = 4
};

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

/* Packed layout: 8-byte magic "R6CAR\0\1\0", u32 version 1, u32 count,
 * u32 record size 144, u32 reserved, then count 144-byte records.
 * On R6_ERR_BUFFER, *count holds the required capacity. */
R6_API int r6_car_catalog_parse(const void *data, size_t size,
                                r6_car_info *cars, size_t capacity,
                                size_t *count);
R6_API int r6_car_catalog_find_model(const r6_car_info *cars, size_t count,
                                     const char *model);
R6_API int r6_car_catalog_find_id(const r6_car_info *cars, size_t count,
                                  uint16_t model_id);

#ifdef __cplusplus
}
#endif

#endif
