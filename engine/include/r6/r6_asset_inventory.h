/* Freestanding reader for shipped asset-tree counts. The derived blob comes
 * from tools/engine/asset_inventory_catalog.py. */
#ifndef R6_ASSET_INVENTORY_H
#define R6_ASSET_INVENTORY_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_ASSET_INVENTORY_ROOTS = 2,
    R6_ASSET_INVENTORY_EXTS = 32,
    R6_ASSET_INVENTORY_MAGICS = 7,
    R6_ASSET_INVENTORY_FOLDERS = 27,
    R6_ASSET_INVENTORY_SHADERS = 40,
    R6_ASSET_INVENTORY_KINDS = 7,
    R6_ASSET_INVENTORY_NAME_CAP = 0x80
};

typedef struct r6_asset_inventory_header {
    uint32_t root_count;
    uint32_t classified[2];
    uint32_t ext_count[2];
    uint32_t magic_count[2];
    uint32_t folder_count[2];
    uint32_t shader_count;
    uint32_t strings_size;
} r6_asset_inventory_header;

R6_API int r6_asset_inventory_parse(const void *data, size_t size,
                                    r6_asset_inventory_header *out);

R6_API int r6_asset_inventory_ext(const void *data, size_t size,
                                  uint32_t index, char *name, size_t capacity,
                                  uint32_t *root, uint32_t *files,
                                  uint32_t *bytes_lo, uint32_t *bytes_hi,
                                  uint32_t *kinds);

R6_API int r6_asset_inventory_magic(const void *data, size_t size,
                                    uint32_t index, char *name,
                                    size_t capacity, uint32_t *root,
                                    uint32_t *count);

R6_API int r6_asset_inventory_folder(const void *data, size_t size,
                                     uint32_t index, char *name,
                                     size_t capacity, uint32_t *root,
                                     uint32_t *files, uint32_t *bytes_lo,
                                     uint32_t *bytes_hi);

/* First exact name match; R6_ERR_NOT_FOUND means no row matched. */
R6_API int r6_asset_inventory_find_ext(const void *data, size_t size,
                                       const char *name, uint32_t *index);

R6_API int r6_asset_inventory_find_folder(const void *data, size_t size,
                                          const char *name, uint32_t *index);

R6_API int r6_asset_inventory_shader(const void *data, size_t size,
                                     uint32_t index, char *path,
                                     size_t capacity, uint32_t *file_size,
                                     unsigned char *head);

#ifdef __cplusplus
}
#endif

#endif
