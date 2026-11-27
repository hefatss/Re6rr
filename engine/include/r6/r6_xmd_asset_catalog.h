/* Freestanding inventory of XMD.001 headers from shipped .TEX/.MDL assets.
 * The blob comes from tools/engine/xmd_asset_catalog.py. Stream contents are
 * not inflated or interpreted by the core; only copied facts cross the bridge.
 */
#ifndef R6_XMD_ASSET_CATALOG_H
#define R6_XMD_ASSET_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_XMD_ASSET_EXT_TEX = 0,
    R6_XMD_ASSET_EXT_MDL = 1,
    R6_XMD_ASSET_WRAP_RAW = 0,
    R6_XMD_ASSET_WRAP_GZIP = 1,
    R6_XMD_ASSET_VERSION = 3
};

typedef struct r6_xmd_asset_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t stream_count;
    uint32_t strings_size;
} r6_xmd_asset_header_t;

typedef struct r6_xmd_asset_file_t {
    uint32_t source_size;
    uint32_t inflated_size;
    uint32_t ext;
    uint32_t wrap;
    uint32_t gzip_flags;
    uint32_t gzip_mtime;
    uint32_t gzip_xfl_os;
    uint32_t expected_size;
    uint32_t xmd_version;
    uint32_t stream_first;
    uint32_t stream_count;
} r6_xmd_asset_file_t;

R6_API int r6_xmd_asset_parse(const void *data, size_t size,
                              r6_xmd_asset_header_t *out);

/* Validates the copied wrap facts, XMD version and stream range. */
R6_API int r6_xmd_asset_file(const void *data, size_t size, uint32_t index,
                             r6_xmd_asset_file_t *out);

/* Copied NUL-terminated relative path from the dump. */
R6_API int r6_xmd_asset_path(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

/* Copied XMD stream offset and size with arithmetic rechecked against the
 * owning file's inflated size. */
R6_API int r6_xmd_asset_stream(const void *data, size_t size, uint32_t index,
                               uint32_t local, uint32_t *offset,
                               uint32_t *size_out);

#ifdef __cplusplus
}
#endif

#endif
