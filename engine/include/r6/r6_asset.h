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

/* Parses every texture header in one NTWD stream. capacity is a texture count. */
R6_API int r6_ntwd_parse(const void *data, size_t size, r6_ntwd_header *out,
                         r6_ntwd_texture *textures, size_t capacity);

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
