/* Asset containers used by WMMT6RR: XMD.001, NDWD meshes, NTWD textures.
 *
 * Parsers are bounds-checked and work on already-inflated bytes. Layouts are
 * documented in docs/ASSETS_NOTES.md and were recovered from the wmn6r.exe
 * loaders in Ghidra.
 */
#ifndef R6_ASSET_H
#define R6_ASSET_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_stream {
    uint32_t offset;
    uint32_t size;
} r6_stream;

/* Parse a gzip header and return the expected inflated size (ISIZE). */
R6_API int r6_gzip_expected_size(const void *data, size_t size,
                                 size_t *out_size);

/* Inflate a gzip stream into caller memory. On R6_ERR_BUFFER, out_size holds
 * the required capacity. On success out_size holds the number of bytes. */
R6_API int r6_gzip_inflate(const void *data, size_t size, void *out,
                           size_t capacity, size_t *out_size);

/* XMD.001: "XMD\0001", u32 version, u32 count, u32 offsets[count]. */
R6_API int r6_xmd_parse(const void *data, size_t size, r6_stream *out,
                        size_t capacity, uint32_t *version, uint32_t *count);

typedef struct r6_ndwd_header {
    uint32_t id;
    uint16_t version;
    uint16_t group_count;
    uint32_t section_size[4];
} r6_ndwd_header;

typedef struct r6_ndwd_group {
    uint32_t offset;
    uint32_t name_offset;
    uint16_t subrecord_count;
    uint32_t subrecord_start;
} r6_ndwd_group;

R6_API int r6_ndwd_parse_header(const void *data, size_t size,
                                r6_ndwd_header *out);
R6_API int r6_ndwd_parse_group(const void *data, size_t size,
                               const r6_ndwd_header *header, uint32_t index,
                               r6_ndwd_group *out);

/* Raw NDWD subrecord and chain record fields. The four tokens are the u32
 * words at sub+0x10..0x1c and are copied verbatim; no material or texture
 * semantics are inferred. Shipped flag-zero chain records are returned as
 * raw records even though the native loader gates on the flag byte. */
typedef struct r6_ndwd_subrecord_t {
    uint32_t offset;
    uint32_t tokens[4];
    uint16_t extra;
    uint32_t chain_offset;
} r6_ndwd_subrecord_t;

typedef struct r6_ndwd_chain_record_t {
    uint32_t offset;
    uint32_t stride;
    uint32_t name_offset;
    uint8_t flag;
} r6_ndwd_chain_record_t;

R6_API int r6_ndwd_parse_subrecord(const void *data, size_t size,
                                   const r6_ndwd_header *header,
                                   const r6_ndwd_group *group,
                                   uint32_t index,
                                   r6_ndwd_subrecord_t *out);

R6_API int r6_ndwd_parse_chain_record(const void *data, size_t size,
                                      const r6_ndwd_header *header,
                                      const r6_ndwd_subrecord_t *sub,
                                      uint32_t index,
                                      r6_ndwd_chain_record_t *out);

/* String table base is 0x30 + sum(section_size[0..3]); offset is relative to
 * that base. On R6_ERR_BUFFER, used holds the required length including NUL. */
R6_API int r6_ndwd_string(const void *data, size_t size,
                          const r6_ndwd_header *header, uint32_t offset,
                          char *out, size_t capacity, size_t *used);

typedef struct r6_ntwd_texture {
    uint32_t header_offset;
    uint32_t data_offset;
    uint32_t data_size;
    uint32_t texture_id;
    uint32_t flags;
    uint16_t width;
    uint16_t height;
    uint16_t header_stride;
    uint8_t faces; /* +0x11: mip-level count; also sizes the eXt/GIDX table skip */
    uint8_t format;
} r6_ntwd_texture;

typedef struct r6_ntwd_header {
    uint8_t type;
    uint16_t texture_count;
} r6_ntwd_header;

/* Parses every texture header in one NTWD/NTLX stream. capacity is a texture
 * count; on R6_ERR_BUFFER, out->texture_count holds the required count. */
R6_API int r6_ntwd_parse(const void *data, size_t size, r6_ntwd_header *out,
                         r6_ntwd_texture *textures, size_t capacity);

/* File-level NTWD/NTLX header facts. `container` is the first four bytes as
 * a little-endian u32 (NTWD = 0x4457544e, NTLX = 0x584c544e); packed0/packed1
 * and first_gidx are copied verbatim. `exact` is the empirical predicate
 * size == payload_offset + entries*payload_size, not a native validator. */
typedef struct r6_nut_container_facts_t {
    uint32_t container;
    uint32_t version;
    uint32_t entries;
    uint64_t total;
    uint32_t payload_size;
    uint32_t descriptor_size;
    uint32_t packed0;
    uint32_t packed1;
    uint64_t first_gidx;
    uint64_t payload_offset;
    uint32_t exact;
} r6_nut_container_facts_t;

R6_API int r6_nut_container_facts(const void *data, size_t size,
                                  r6_nut_container_facts_t *out);

/* Derived mip-payload layout for one NTWD/NTLX texture descriptor. Sizes come
 * from the shipped 16-byte-aligned mip model; available_levels is clipped by
 * the descriptor payload size. No file or pixel data is read. */
typedef struct r6_nut_layout_facts_t {
    uint64_t expected_size;     /* full declared chain, including cube faces */
    uint64_t face_size;         /* expected_size / face count */
    uint64_t level0_bytes;      /* aligned first level of one face */
    uint32_t declared_levels;   /* descriptor +0x11 */
    uint32_t available_levels;  /* levels present in data_size */
    uint32_t cube;              /* 1 when flags bit 9 or 0x11 is set */
} r6_nut_layout_facts_t;

R6_API int r6_nut_layout_facts(const r6_ntwd_texture *texture,
                               r6_nut_layout_facts_t *out);

/* Decode one mip level / cube face to RGBA8. On R6_ERR_BUFFER, out_size holds
 * the required capacity. data is an inflated NTWD/NTLX container; texture may
 * come from r6_ntwd_parse or an equivalent host-built descriptor. */
R6_API int r6_nut_decode_rgba(const void *data, size_t size,
                              const r6_ntwd_texture *texture, uint32_t level,
                              uint32_t face, void *out, size_t capacity,
                              size_t *out_size);

#ifdef __cplusplus
}
#endif

#endif
