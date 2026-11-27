/* Freestanding reader for the shipped NSXR (.nsh) container and its DXBC
 * chunk tables. No files, allocation or D3D objects: the host supplies bytes.
 * SHDR/RDEF/ISGN/OSGN payload interpretation stays in the Python recon tools.
 */
#ifndef R6_NSH_H
#define R6_NSH_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_NSH_HEADER_SIZE = 0x80,
    R6_NSH_RECORD_SIZE = 0x10,
    R6_NSH_RECORD_MAX = 2,
    R6_NSH_CHUNK_MAX = 8,
    R6_DXBC_HEADER_SIZE = 0x20
};

typedef struct r6_nsh_chunk_t {
    uint32_t tag;
    uint32_t offset;
    uint32_t size;
    uint32_t data_offset;
} r6_nsh_chunk_t;

typedef struct r6_nsh_record_t {
    uint32_t offset;
    uint32_t count;
    uint32_t dxbc_size;
    uint32_t reserved;
    uint32_t dxbc_offset;
    uint32_t dxbc_version;
    uint32_t dxbc_actual_size;
    uint32_t chunk_count;
    uint8_t digest[16];
    r6_nsh_chunk_t chunks[R6_NSH_CHUNK_MAX];
} r6_nsh_record_t;

typedef struct r6_nsh_t {
    uint32_t file_size;
    uint32_t version;
    uint32_t subversion;
    uint32_t flags;
    uint32_t record_count;
    uint32_t table[5];
    r6_nsh_record_t records[R6_NSH_RECORD_MAX];
} r6_nsh_t;

R6_API int r6_nsh_parse(const void *data, size_t size, r6_nsh_t *out);

/* First chunk with the given four-CC tag in one parsed record. */
R6_API int r6_nsh_chunk_find(const r6_nsh_t *nsh, uint32_t record,
                             uint32_t tag, r6_nsh_chunk_t *out);

/* Sum of the 29-u32 DX10 STAT fields across the 446 shipped DXBC records.
 * Field names are copied verbatim from nsxr_shader.STAT_FIELDS; unknown_* are
 * kept rather than interpreted. No STAT chunk is read or rewritten here. */
typedef struct r6_dxbc_stat_facts_t {
    uint32_t record_count;
    uint32_t instruction_count;
    uint32_t temp_register_count;
    uint32_t unknown_a;
    uint32_t dcl_count;
    uint32_t flt_instruction_count;
    uint32_t int_instruction_count;
    uint32_t uint_instruction_count;
    uint32_t static_flow_control_count;
    uint32_t dynamic_flow_control_count;
    uint32_t unknown_b;
    uint32_t temp_array_count;
    uint32_t array_instruction_count;
    uint32_t cut_instruction_count;
    uint32_t emit_instruction_count;
    uint32_t sample_tex_count;
    uint32_t load_tex_count;
    uint32_t cmp_tex_count;
    uint32_t sample_bias_tex_count;
    uint32_t sample_grad_tex_count;
    uint32_t mov_instruction_count;
    uint32_t unknown_c;
    uint32_t conv_instruction_count;
    uint32_t unknown_d;
    uint32_t input_prim_count;
    uint32_t gs_output_topology;
    uint32_t gs_max_output_vtx_count;
    uint32_t unknown_e0;
    uint32_t unknown_e1;
    uint32_t unknown_e2;
} r6_dxbc_stat_facts_t;

R6_API void r6_dxbc_stat_facts(r6_dxbc_stat_facts_t *out);

#ifdef __cplusplus
}
#endif

#endif
