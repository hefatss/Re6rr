/* Bounded NSXR / DXBC container reader. Derived from tools/engine/nsxr_shader.py
 * and the shipped 223 .nsh files; no CRT, files or graphics device. */

#include "r6/r6_nsh.h"

#include "core/internal.h"

static uint32_t nsh_u32(const unsigned char *bytes, size_t at) {
    return (uint32_t)bytes[at] |
           ((uint32_t)bytes[at + 1] << 8) |
           ((uint32_t)bytes[at + 2] << 16) |
           ((uint32_t)bytes[at + 3] << 24);
}

int r6_nsh_parse(const void *data, size_t size, r6_nsh_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t index;
    uint32_t chunk;
    if (!bytes || !out || size < R6_NSH_HEADER_SIZE ||
        bytes[0] != 'N' || bytes[1] != 'S' || bytes[2] != 'X' ||
        bytes[3] != 'R' || size > 0xFFFFFFFFull) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    out->file_size = nsh_u32(bytes, 4);
    if (out->file_size != (uint32_t)size) {
        return R6_ERR_FORMAT;
    }
    out->version = nsh_u32(bytes, 8);
    out->subversion = nsh_u32(bytes, 0x0C);
    out->flags = nsh_u32(bytes, 0x20);
    out->record_count = nsh_u32(bytes, 0x24);
    for (index = 0; index < 5u; index++) {
        out->table[index] = nsh_u32(bytes, 0x28 + index * 4u);
    }
    if (out->record_count > R6_NSH_RECORD_MAX ||
        (uint64_t)R6_NSH_HEADER_SIZE +
            (uint64_t)out->record_count * R6_NSH_RECORD_SIZE > size) {
        return R6_ERR_FORMAT;
    }
    for (index = 0; index < out->record_count; index++) {
        r6_nsh_record_t *record = &out->records[index];
        size_t at = R6_NSH_HEADER_SIZE + index * R6_NSH_RECORD_SIZE;
        uint64_t dxbc_at;
        uint64_t blob_end;
        uint32_t relative;
        record->offset = nsh_u32(bytes, at);
        record->count = nsh_u32(bytes, at + 4u);
        record->dxbc_size = nsh_u32(bytes, at + 8u);
        record->reserved = nsh_u32(bytes, at + 0x0Cu);
        dxbc_at = (uint64_t)record->offset + 0x20u;
        if (dxbc_at > size || size - (size_t)dxbc_at < R6_DXBC_HEADER_SIZE ||
            bytes[dxbc_at] != 'D' || bytes[dxbc_at + 1] != 'X' ||
            bytes[dxbc_at + 2] != 'B' || bytes[dxbc_at + 3] != 'C') {
            return R6_ERR_FORMAT;
        }
        record->dxbc_offset = (uint32_t)dxbc_at;
        r6_memcpy(record->digest, bytes + dxbc_at + 4u, sizeof(record->digest));
        record->dxbc_version = nsh_u32(bytes, (size_t)dxbc_at + 0x14u);
        record->dxbc_actual_size = nsh_u32(bytes, (size_t)dxbc_at + 0x18u);
        record->chunk_count = nsh_u32(bytes, (size_t)dxbc_at + 0x1Cu);
        if (record->dxbc_actual_size < R6_DXBC_HEADER_SIZE ||
            (uint64_t)dxbc_at + record->dxbc_actual_size > size ||
            record->dxbc_size != record->dxbc_actual_size ||
            record->chunk_count > R6_NSH_CHUNK_MAX ||
            (uint64_t)R6_DXBC_HEADER_SIZE +
                (uint64_t)record->chunk_count * 4u > record->dxbc_actual_size) {
            return R6_ERR_FORMAT;
        }
        blob_end = dxbc_at + record->dxbc_actual_size;
        for (chunk = 0; chunk < record->chunk_count; chunk++) {
            r6_nsh_chunk_t *part = &record->chunks[chunk];
            uint64_t start;
            relative = nsh_u32(bytes, (size_t)dxbc_at + R6_DXBC_HEADER_SIZE +
                                     chunk * 4u);
            if (relative > record->dxbc_actual_size) {
                return R6_ERR_FORMAT;
            }
            start = dxbc_at + relative;
            if (start > blob_end || blob_end - start < 8u) {
                return R6_ERR_FORMAT;
            }
            r6_memcpy(&part->tag, bytes + start, sizeof(part->tag));
            part->offset = relative;
            part->size = nsh_u32(bytes, (size_t)start + 4u);
            if ((uint64_t)part->size > blob_end - start - 8u) {
                return R6_ERR_FORMAT;
            }
            part->data_offset = (uint32_t)(start + 8u);
        }
    }
    return R6_OK;
}

int r6_nsh_chunk_find(const r6_nsh_t *nsh, uint32_t record, uint32_t tag,
                      r6_nsh_chunk_t *out) {
    uint32_t at;
    if (!nsh || !out || record >= nsh->record_count) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < nsh->records[record].chunk_count; at++) {
        const r6_nsh_chunk_t *chunk = &nsh->records[record].chunks[at];
        if (chunk->tag == tag) {
            r6_memcpy(out, chunk, sizeof(*out));
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

void r6_dxbc_stat_facts(r6_dxbc_stat_facts_t *out) {
    if (!out) {
        return;
    }
    r6_memset(out, 0, sizeof(*out));
    out->record_count = 446u;
    out->instruction_count = 20563u;
    out->temp_register_count = 1083u;
    out->unknown_a = 0u;
    out->dcl_count = 2888u;
    out->flt_instruction_count = 6010u;
    out->int_instruction_count = 1722u;
    out->uint_instruction_count = 68u;
    out->static_flow_control_count = 3175u;
    out->dynamic_flow_control_count = 31u;
    out->unknown_b = 0u;
    out->temp_array_count = 232u;
    out->array_instruction_count = 234u;
    out->cut_instruction_count = 0u;
    out->emit_instruction_count = 0u;
    out->sample_tex_count = 680u;
    out->load_tex_count = 0u;
    out->cmp_tex_count = 0u;
    out->sample_bias_tex_count = 0u;
    out->sample_grad_tex_count = 0u;
    out->mov_instruction_count = 7698u;
    out->unknown_c = 57u;
    out->conv_instruction_count = 126u;
    out->unknown_d = 0u;
    out->input_prim_count = 0u;
    out->gs_output_topology = 0u;
    out->gs_max_output_vtx_count = 0u;
    out->unknown_e0 = 0u;
    out->unknown_e1 = 0u;
    out->unknown_e2 = 0u;
}

void r6_dxbc_reflection_facts(r6_dxbc_reflection_facts_t *out) {
    if (!out) {
        return;
    }
    r6_memset(out, 0, sizeof(*out));
    out->record_count = 446u;
    out->vertex_count = 223u;
    out->pixel_count = 223u;
    out->target_version = 0x0400u;
    out->flags = 0x108u;
    out->cbuffer_count = 797u;
    out->cbuffer_bytes = 64976u;
    out->variable_count = 2029u;
    out->resource_count = 1849u;
    out->resource_cbuffer = 797u;
    out->resource_texture = 526u;
    out->resource_sampler = 526u;
    out->class_scalar = 292u;
    out->class_vector = 1011u;
    out->class_matrix_rows = 726u;
    out->type_float = 1883u;
    out->type_uint = 146u;
    out->nonzero_member_offsets = 0u;
    out->dimension_0 = 1323u;
    out->dimension_4 = 476u;
    out->dimension_9 = 50u;
    out->sample_count_0 = 1323u;
    out->sample_count_all = 526u;
}

int r6_dxbc_reflection_creator(char *out, size_t capacity) {
    static const char creator[] =
        "Microsoft (R) HLSL Shader Compiler 9.29.952.3111";
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (capacity < sizeof(creator)) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, creator, sizeof(creator));
    return R6_OK;
}
