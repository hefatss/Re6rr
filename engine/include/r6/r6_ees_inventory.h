/* Freestanding inventory of shipped .EES scene-file headers and array facts.
 * The blob comes from tools/engine/ees_inventory_catalog.py. Array contents
 * and runtime camera/car field semantics are not interpreted. */
#ifndef R6_EES_INVENTORY_H
#define R6_EES_INVENTORY_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_EES_INVENTORY_KIND_CAM = 0,
    R6_EES_INVENTORY_KIND_CAR = 1,
    R6_EES_INVENTORY_NAME_CAP = 64
};

typedef struct r6_ees_inventory_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t array_count;
    uint32_t strings_size;
} r6_ees_inventory_header_t;

typedef struct r6_ees_inventory_file_t {
    uint32_t file_size;
    uint32_t kind;
    uint32_t version;
    uint32_t count;
    uint32_t effect_count;
    uint32_t header_size;
    uint32_t array_first;
    uint32_t array_count;
} r6_ees_inventory_file_t;

typedef struct r6_ees_inventory_array_t {
    uint32_t count;
    uint32_t stride;
    uint32_t offset;
    uint32_t size;
} r6_ees_inventory_array_t;

R6_API int r6_ees_inventory_parse(const void *data, size_t size,
                                  r6_ees_inventory_header_t *out);

R6_API int r6_ees_inventory_file(const void *data, size_t size,
                                 uint32_t index,
                                 r6_ees_inventory_file_t *out);

/* Copied NUL-terminated scene-relative path. */
R6_API int r6_ees_inventory_path(const void *data, size_t size,
                                 uint32_t index, char *out, size_t capacity);

/* Copied array name, count, stride, offset and size with arithmetic rechecked
 * against the owning file header. */
R6_API int r6_ees_inventory_array(const void *data, size_t size,
                                  uint32_t index, char *name, size_t capacity,
                                  r6_ees_inventory_array_t *out);

#ifdef __cplusplus
}
#endif

#endif
