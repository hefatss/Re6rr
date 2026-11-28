/* Freestanding inventory of AMUpdater TGA header facts. The blob comes from
 * tools/engine/tga_inventory_catalog.py. Header fields, sizes and footer
 * presence are copied; pixel bytes are not. */
#ifndef R6_TGA_INVENTORY_CATALOG_H
#define R6_TGA_INVENTORY_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_tga_inventory_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t string_size;
    uint32_t total_bytes;
    uint32_t raw_count;
    uint32_t rle_count;
    uint32_t footer_count;
} r6_tga_inventory_header_t;

typedef struct r6_tga_inventory_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t kind;
    uint32_t width;
    uint32_t height;
    uint32_t bpp;
    uint32_t descriptor;
    uint32_t pixels;
    uint32_t raw_exact;
} r6_tga_inventory_file_t;

R6_API int r6_tga_inventory_parse(const void *data, size_t size,
                                  r6_tga_inventory_header_t *out);

R6_API int r6_tga_inventory_file(const void *data, size_t size, uint32_t index,
                                 r6_tga_inventory_file_t *out);

R6_API int r6_tga_inventory_path(const void *data, size_t size, uint32_t index,
                                 char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
