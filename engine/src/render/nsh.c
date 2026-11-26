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
