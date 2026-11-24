/* Packed customization catalog generated from shipped Lua and name tables.
 *
 * The freestanding core owns no data: r6_custom_catalog_parse() only validates
 * a host-owned .r6custom blob and returns typed views into it. Record accessors
 * copy into caller storage so unaligned blobs stay safe.
 */
#ifndef R6_CUSTOM_H
#define R6_CUSTOM_H

#include <stddef.h>
#include <stdint.h>

#include "r6/r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_CUSTOM_HEADER_SIZE 32
#define R6_CUSTOM_COLOR_SIZE 96
#define R6_CUSTOM_WHEEL_SIZE 48
#define R6_CUSTOM_AERO_SIZE 64
#define R6_CUSTOM_TUNE_SIZE 160
#define R6_CUSTOM_TIRE_SIZE 8
#define R6_CUSTOM_NAME_SIZE 24
#define R6_CUSTOM_PART_NAME_SIZE 48
#define R6_CUSTOM_DEFAULT_COLORS 11
#define R6_CUSTOM_CUSTOM_COLORS 40

enum r6_custom_section {
    R6_CUSTOM_SECTION_COLOR = 0,
    R6_CUSTOM_SECTION_WHEEL = 1,
    R6_CUSTOM_SECTION_AERO = 2,
    R6_CUSTOM_SECTION_TUNE = 3,
    R6_CUSTOM_SECTION_TIRE = 4
};

enum r6_custom_wheel_flags {
    R6_CUSTOM_WHEEL_ASSET = 1
};

enum r6_custom_aero_flags {
    R6_CUSTOM_AERO_AERO = 1,
    R6_CUSTOM_AERO_WING = 2,
    R6_CUSTOM_AERO_BONNET = 4,
    R6_CUSTOM_AERO_SPOILER = 8,
    R6_CUSTOM_AERO_DIFFUSER = 16,
    R6_CUSTOM_AERO_SKIRT = 32,
    R6_CUSTOM_AERO_WHEEL = 64
};

enum r6_custom_tire_kind {
    R6_CUSTOM_TIRE_WHEEL_SCALE = 0,
    R6_CUSTOM_TIRE_WIDTH_SCALE = 1,
    R6_CUSTOM_TIRE_DIAMETER = 2
};

typedef struct r6_custom_color {
    uint16_t id;              /* LibraryColor.lua type index */
    uint16_t icon;
    uint16_t feel;
    uint16_t reserved;
    float body0[4];
    float body1[4];
    float spec[4];
    float params[4];          /* specular, reflect, cosinepower, fresnel */
    char name[R6_CUSTOM_NAME_SIZE]; /* CP932 message-DB label */
} r6_custom_color;

typedef struct r6_custom_wheel {
    uint16_t id;              /* index in the SWH_* name table */
    uint16_t reserved;
    char name[R6_CUSTOM_NAME_SIZE];
    uint32_t flags;
    uint32_t reserved2[4];
} r6_custom_wheel;

typedef struct r6_custom_aero {
    uint16_t id;              /* index in the CAR_PARTS_ID_* name table */
    uint16_t reserved;
    char name[R6_CUSTOM_PART_NAME_SIZE];
    uint32_t flags;
    uint32_t reserved2[2];
} r6_custom_aero;

typedef struct r6_custom_tune {
    char model[R6_CUSTOM_NAME_SIZE];
    uint16_t aero_category;
    uint16_t limited_parts;
    uint8_t pure_wheel_front;
    uint8_t pure_wheel_rear;
    uint8_t custom_wheel_front;
    uint8_t custom_wheel_rear;
    uint8_t change_tuning_disp;
    uint8_t custom_gt_wing;
    uint16_t wing_a_h;
    uint16_t wing_n;
    uint16_t default_color_count;
    uint16_t custom_color_count;
    uint16_t default_color_ids[R6_CUSTOM_DEFAULT_COLORS];
    uint16_t custom_color_ids[R6_CUSTOM_CUSTOM_COLORS];
    uint32_t flags;           /* car dress-up/custom colour/supercharger */
    uint32_t reserved;
    uint8_t pad[8];
} r6_custom_tune;

typedef struct r6_custom_tire {
    uint16_t kind;
    uint16_t index;
    float value;
} r6_custom_tire;

typedef struct r6_custom_catalog {
    const r6_custom_color *colors;
    const r6_custom_wheel *wheels;
    const r6_custom_aero *aeros;
    const r6_custom_tune *tunes;
    const r6_custom_tire *tires;
    size_t color_count;
    size_t wheel_count;
    size_t aero_count;
    size_t tune_count;
    size_t tire_count;
} r6_custom_catalog;

R6_API int r6_custom_catalog_parse(const void *data, size_t size,
                                    r6_custom_catalog *out);
R6_API int r6_custom_catalog_color(const r6_custom_catalog *catalog,
                                   size_t index, r6_custom_color *out);
R6_API int r6_custom_catalog_wheel(const r6_custom_catalog *catalog,
                                   size_t index, r6_custom_wheel *out);
R6_API int r6_custom_catalog_aero(const r6_custom_catalog *catalog,
                                  size_t index, r6_custom_aero *out);
R6_API int r6_custom_catalog_tune(const r6_custom_catalog *catalog,
                                  size_t index, r6_custom_tune *out);
R6_API int r6_custom_catalog_tire(const r6_custom_catalog *catalog,
                                  size_t index, r6_custom_tire *out);
R6_API int r6_custom_catalog_find_color(const r6_custom_catalog *catalog,
                                        uint16_t id);
R6_API int r6_custom_catalog_find_wheel(const r6_custom_catalog *catalog,
                                        const char *name);
R6_API int r6_custom_catalog_find_aero(const r6_custom_catalog *catalog,
                                       const char *name);
R6_API int r6_custom_catalog_find_tune(const r6_custom_catalog *catalog,
                                       const char *model);

#ifdef __cplusplus
}
#endif

#endif
