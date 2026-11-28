/* Freestanding inventory of the shipped SDL controller database.
 * The blob comes from tools/engine/sdl_db_catalog.py. Paths, line kinds,
 * verbatim ASCII lines, id/name/platform spans and field counts are copied.
 * Device identity, SDL button meaning, platform priority and remap behavior
 * stay unparsed. */
#ifndef R6_SDL_DB_CATALOG_H
#define R6_SDL_DB_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_sdl_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t line_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t comment_count;
    uint32_t blank_count;
    uint32_t path_offset;
    uint32_t path_length;
} r6_sdl_header_t;

typedef struct r6_sdl_line_t {
    uint32_t text_offset;
    uint32_t text_length;
    uint32_t kind;
    uint32_t line;
} r6_sdl_line_t;

typedef struct r6_sdl_row_t {
    uint32_t id_offset;
    uint32_t id_length;
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t platform_offset;
    uint32_t platform_length;
    uint32_t fields;
    uint32_t line;
} r6_sdl_row_t;

R6_API int r6_sdl_parse(const void *data, size_t size, r6_sdl_header_t *out);

R6_API int r6_sdl_path(const void *data, size_t size, char *out,
                       size_t capacity);

R6_API int r6_sdl_line(const void *data, size_t size, uint32_t index,
                       r6_sdl_line_t *out);

R6_API int r6_sdl_line_text(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_sdl_row(const void *data, size_t size, uint32_t index,
                      r6_sdl_row_t *out);

R6_API int r6_sdl_field_text(const void *data, size_t size, uint32_t index,
                             uint32_t field, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
