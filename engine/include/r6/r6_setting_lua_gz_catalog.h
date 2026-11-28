/* Freestanding inventory of shipped root setting.lua.gz structural facts.
 * The blob comes from tools/engine/setting_lua_gz_catalog.py. Paths, gzip
 * header words and copied ASCII key/integer rows are stored; compressed
 * deflate bytes are not stored and no setting meaning is inferred. */
#ifndef R6_SETTING_LUA_GZ_CATALOG_H
#define R6_SETTING_LUA_GZ_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_setting_lua_gz_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t key_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t inflated_bytes;
    uint32_t line_count;
} r6_setting_lua_gz_header_t;

typedef struct r6_setting_lua_gz_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t compressed_size;
    uint32_t mtime;
    uint32_t crc32;
    uint32_t inflated_size;
} r6_setting_lua_gz_file_t;

R6_API int r6_setting_lua_gz_parse(
    const void *data, size_t size, r6_setting_lua_gz_header_t *out);

R6_API int r6_setting_lua_gz_file(const void *data, size_t size,
                                  uint32_t index,
                                  r6_setting_lua_gz_file_t *out);

R6_API int r6_setting_lua_gz_path(const void *data, size_t size,
                                  uint32_t index, char *out,
                                  size_t capacity);

R6_API int r6_setting_lua_gz_key(const void *data, size_t size,
                                 uint32_t index, char *out, size_t capacity);

R6_API int r6_setting_lua_gz_value(const void *data, size_t size,
                                   uint32_t file_index, uint32_t key_index,
                                   char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
