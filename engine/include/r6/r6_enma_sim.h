/* Freestanding reader for shipped Enma input-simulation facts. The blob comes
 * from tools/engine/enma_sim_catalog.py; no DLL is loaded or called. */
#ifndef R6_ENMA_SIM_H
#define R6_ENMA_SIM_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_ENMA_SIM_GETTERS = 6,
    R6_ENMA_SIM_HITS = 4,
    R6_ENMA_SIM_CONFIG_SIZE = 4096,
    R6_ENMA_SIM_NAME_CAP = 256,
    R6_ENMA_SIM_BASE_FLOAT = 0,
    R6_ENMA_SIM_BASE_INT = 1,
    R6_ENMA_SIM_BASE_BOOL = 2
};

typedef struct r6_enma_sim_header {
    uint32_t version;
    uint32_t getter_count;
    uint32_t hit_count;
    uint32_t config_size;
    uint32_t strings_size;
    uint32_t strings_off;
} r6_enma_sim_header;

R6_API int r6_enma_sim_parse(const void *data, size_t size,
                             r6_enma_sim_header *out);

R6_API int r6_enma_sim_getter(const void *data, size_t size, uint32_t index,
                              char *name, size_t name_capacity,
                              char *export_name, size_t export_capacity,
                              uint32_t *hit_first, uint32_t *hit_count,
                              uint32_t *baseline_kind,
                              uint32_t *baseline_bits);

R6_API int r6_enma_sim_hit(const void *data, size_t size, uint32_t index,
                           uint32_t *offset, uint32_t *value_bits);

R6_API int r6_enma_sim_config(const void *data, size_t size,
                              unsigned char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
