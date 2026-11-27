/* Reader for the fixed-layout GLSL binding manifest emitted by
 * tools/engine/glsl_manifest.py. The core only validates and copies metadata;
 * the host owns the buffer and all GL objects. No files, CRT or libm. */
#ifndef R6_GLSL_MANIFEST_H
#define R6_GLSL_MANIFEST_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"
#include "r6_glsl.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_GLSL_BINDINGS_VERSION = 1,
    R6_GLSL_STAGE_VERTEX = 0,
    R6_GLSL_STAGE_PIXEL = 1,
    R6_GLSL_STAGE_UBO = 0x100
};

typedef struct r6_glsl_bindings_view {
    const unsigned char *data;
    size_t size;
    uint32_t count;
    uint32_t records;
    uint32_t cbuffers;
    uint32_t regions;
    uint32_t samplers;
    uint32_t strings;
} r6_glsl_bindings_view;

typedef struct r6_glsl_bindings_record_info {
    uint32_t flags;             /* stage plus R6_GLSL_STAGE_UBO */
    uint16_t cbuffers;
    uint16_t samplers;
    uint32_t cbuffer_first;
    uint32_t name_off;
} r6_glsl_bindings_record_info;

typedef struct r6_glsl_bindings_cbuffer_info {
    uint32_t binding;
    uint32_t name_off;
    uint32_t size;
    uint16_t slots;
    uint16_t ubo;
    uint16_t regions;
    uint32_t region_first;
} r6_glsl_bindings_cbuffer_info;

typedef struct r6_glsl_bindings_sampler_info {
    uint32_t unit;
    uint32_t texture_off;
    uint32_t sampler_off;
} r6_glsl_bindings_sampler_info;

/* Aggregate GLES lowering facts for all 446 shipped SHDR records.
 * total/direct/lower/control/texture are instruction counts; opcodes is the
 * number of distinct classified opcodes and unknown must be zero. */
typedef struct r6_glsl_coverage_facts_t {
    uint32_t total;
    uint32_t direct;
    uint32_t lower;
    uint32_t control;
    uint32_t texture;
    uint32_t opcodes;
    uint32_t unknown;
} r6_glsl_coverage_facts_t;

R6_API void r6_glsl_coverage_facts(r6_glsl_coverage_facts_t *out);

/* Packed form stored in the manifest; r6_glsl_region uses a u32 size. */
typedef struct r6_glsl_manifest_region {
    uint32_t offset;
    uint16_t size;
    uint8_t kind;
    uint8_t type;
} r6_glsl_manifest_region;

R6_API int r6_glsl_bindings_init(r6_glsl_bindings_view *view,
                                 const void *data, size_t size);

R6_API int r6_glsl_bindings_get_record(const r6_glsl_bindings_view *view,
                                       uint32_t index,
                                       r6_glsl_bindings_record_info *out);

R6_API int r6_glsl_bindings_get_cbuffer(
    const r6_glsl_bindings_view *view,
    const r6_glsl_bindings_record_info *record, uint32_t index,
    r6_glsl_bindings_cbuffer_info *out);

R6_API int r6_glsl_bindings_region(const r6_glsl_bindings_view *view,
                                   const r6_glsl_bindings_cbuffer_info *block,
                                   uint32_t index,
                                   r6_glsl_manifest_region *out);

R6_API int r6_glsl_bindings_get_sampler(
    const r6_glsl_bindings_view *view,
    const r6_glsl_bindings_record_info *record, uint32_t index,
    r6_glsl_bindings_sampler_info *out);

/* First record whose copied shader name matches exactly. */
R6_API int r6_glsl_bindings_find_record(const r6_glsl_bindings_view *view,
                                        const char *name, uint32_t *index);

/* NULL when offset is outside the buffer or the string is unterminated. */
R6_API const char *r6_glsl_bindings_name(const r6_glsl_bindings_view *view,
                                         uint32_t offset);

#ifdef __cplusplus
}
#endif

#endif
