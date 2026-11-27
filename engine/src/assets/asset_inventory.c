/* Bounded reader for the derived asset inventory. No dump traversal or file
 * reads occur inside the core; the host supplies one derived blob. */

#include "r6/r6_asset_inventory.h"

#include "core/internal.h"

static const unsigned char asset_inventory_magic[8] = {
    'R', '6', 'A', 'I', 'V', 0, 1, 0
};

static int asset_header(const void *data, size_t size,
                        r6_asset_inventory_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t ext_off = 60u;
    uint32_t magic_off = ext_off + R6_ASSET_INVENTORY_EXTS * 48u;
    uint32_t folder_off = magic_off + R6_ASSET_INVENTORY_MAGICS * 12u;
    uint32_t shader_off = folder_off + R6_ASSET_INVENTORY_FOLDERS * 20u;
    uint32_t strings_off;
    if (!bytes || !out || size < 60u ||
        r6_memcmp(bytes, asset_inventory_magic,
                  sizeof(asset_inventory_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_ASSET_INVENTORY_ROOTS ||
        r6_u32(bytes, 24) + r6_u32(bytes, 28) != R6_ASSET_INVENTORY_EXTS ||
        r6_u32(bytes, 32) + r6_u32(bytes, 36) != R6_ASSET_INVENTORY_MAGICS ||
        r6_u32(bytes, 40) + r6_u32(bytes, 44) != R6_ASSET_INVENTORY_FOLDERS ||
        r6_u32(bytes, 48) != R6_ASSET_INVENTORY_SHADERS) {
        return R6_ERR_FORMAT;
    }
    strings_off = r6_u32(bytes, 52);
    if (strings_off != shader_off + R6_ASSET_INVENTORY_SHADERS * 24u ||
        !r6_u32(bytes, 56) ||
        (uint64_t)strings_off + r6_u32(bytes, 56) != size) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->root_count = r6_u32(bytes, 12);
    out->classified[0] = r6_u32(bytes, 16);
    out->classified[1] = r6_u32(bytes, 20);
    out->ext_count[0] = r6_u32(bytes, 24);
    out->ext_count[1] = r6_u32(bytes, 28);
    out->magic_count[0] = r6_u32(bytes, 32);
    out->magic_count[1] = r6_u32(bytes, 36);
    out->folder_count[0] = r6_u32(bytes, 40);
    out->folder_count[1] = r6_u32(bytes, 44);
    out->shader_count = r6_u32(bytes, 48);
    out->strings_size = r6_u32(bytes, 56);
    return R6_OK;
}

static int asset_name(const unsigned char *bytes, size_t size,
                      uint32_t strings_off, uint32_t offset, char *out,
                      size_t capacity) {
    uint32_t at = offset;
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (offset < strings_off || offset >= size) {
        return R6_ERR_FORMAT;
    }
    while (at < size && bytes[at]) {
        at++;
    }
    if (at == size || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, at - offset);
    out[at - offset] = 0;
    return R6_OK;
}

static int asset_rows(const void *data, size_t size, uint32_t index,
                      uint32_t stride, uint32_t count, uint32_t base,
                      const unsigned char **bytes, uint32_t *row_off,
                      uint32_t *strings_off) {
    r6_asset_inventory_header header;
    int result = asset_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = base + index * stride;
    *strings_off = r6_u32(*bytes, 52);
    return R6_OK;
}

int r6_asset_inventory_parse(const void *data, size_t size,
                             r6_asset_inventory_header *out) {
    return asset_header(data, size, out);
}

int r6_asset_inventory_ext(const void *data, size_t size, uint32_t index,
                           char *name, size_t capacity, uint32_t *root,
                           uint32_t *files, uint32_t *bytes_lo,
                           uint32_t *bytes_hi, uint32_t *kinds) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t strings_off;
    uint32_t at;
    int result = asset_rows(data, size, index, 48u,
                            R6_ASSET_INVENTORY_EXTS, 60u,
                            &bytes, &row_off, &strings_off);
    if (result != R6_OK) {
        return result;
    }
    if (r6_u32(bytes, row_off) >= R6_ASSET_INVENTORY_ROOTS) {
        return R6_ERR_FORMAT;
    }
    result = asset_name(bytes, size, strings_off,
                        r6_u32(bytes, row_off + 4u), name, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (root) {
        *root = r6_u32(bytes, row_off);
    }
    if (files) {
        *files = r6_u32(bytes, row_off + 8u);
    }
    if (bytes_lo) {
        *bytes_lo = r6_u32(bytes, row_off + 12u);
    }
    if (bytes_hi) {
        *bytes_hi = r6_u32(bytes, row_off + 16u);
    }
    if (kinds) {
        for (at = 0; at < R6_ASSET_INVENTORY_KINDS; at++) {
            kinds[at] = r6_u32(bytes, row_off + 20u + at * 4u);
        }
    }
    return R6_OK;
}

int r6_asset_inventory_magic(const void *data, size_t size, uint32_t index,
                             char *name, size_t capacity, uint32_t *root,
                             uint32_t *count) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t strings_off;
    int result = asset_rows(data, size, index, 12u,
                            R6_ASSET_INVENTORY_MAGICS,
                            60u + R6_ASSET_INVENTORY_EXTS * 48u,
                            &bytes, &row_off, &strings_off);
    if (result != R6_OK) {
        return result;
    }
    if (r6_u32(bytes, row_off) >= R6_ASSET_INVENTORY_ROOTS) {
        return R6_ERR_FORMAT;
    }
    result = asset_name(bytes, size, strings_off,
                        r6_u32(bytes, row_off + 4u), name, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (root) {
        *root = r6_u32(bytes, row_off);
    }
    if (count) {
        *count = r6_u32(bytes, row_off + 8u);
    }
    return R6_OK;
}

int r6_asset_inventory_folder(const void *data, size_t size, uint32_t index,
                              char *name, size_t capacity, uint32_t *root,
                              uint32_t *files, uint32_t *bytes_lo,
                              uint32_t *bytes_hi) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t strings_off;
    int result = asset_rows(data, size, index, 20u,
                            R6_ASSET_INVENTORY_FOLDERS,
                            60u + R6_ASSET_INVENTORY_EXTS * 48u +
                                R6_ASSET_INVENTORY_MAGICS * 12u,
                            &bytes, &row_off, &strings_off);
    if (result != R6_OK) {
        return result;
    }
    if (r6_u32(bytes, row_off) >= R6_ASSET_INVENTORY_ROOTS) {
        return R6_ERR_FORMAT;
    }
    result = asset_name(bytes, size, strings_off,
                        r6_u32(bytes, row_off + 4u), name, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (root) {
        *root = r6_u32(bytes, row_off);
    }
    if (files) {
        *files = r6_u32(bytes, row_off + 8u);
    }
    if (bytes_lo) {
        *bytes_lo = r6_u32(bytes, row_off + 12u);
    }
    if (bytes_hi) {
        *bytes_hi = r6_u32(bytes, row_off + 16u);
    }
    return R6_OK;
}

static int asset_find(const void *data, size_t size, const char *name,
                      uint32_t count, uint32_t stride, uint32_t base,
                      uint32_t *index) {
    uint32_t at;
    size_t wanted;
    if (!name) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < count; at++) {
        const unsigned char *bytes = NULL;
        uint32_t row_off = 0;
        uint32_t strings_off = 0;
        char found[R6_ASSET_INVENTORY_NAME_CAP];
        int result = asset_rows(data, size, at, stride, count, base, &bytes,
                                &row_off, &strings_off);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        result = asset_name(bytes, size, strings_off,
                            r6_u32(bytes, row_off + 4u), found,
                            sizeof(found));
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(found) == wanted &&
            r6_memcmp(found, name, wanted) == 0) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_asset_inventory_find_ext(const void *data, size_t size,
                                const char *name, uint32_t *index) {
    return asset_find(data, size, name, R6_ASSET_INVENTORY_EXTS, 48u, 60u,
                      index);
}

int r6_asset_inventory_find_folder(const void *data, size_t size,
                                   const char *name, uint32_t *index) {
    return asset_find(data, size, name, R6_ASSET_INVENTORY_FOLDERS, 20u,
                      60u + R6_ASSET_INVENTORY_EXTS * 48u +
                          R6_ASSET_INVENTORY_MAGICS * 12u, index);
}

int r6_asset_inventory_find_magic(const void *data, size_t size,
                                  const char *name, uint32_t *index) {
    return asset_find(data, size, name, R6_ASSET_INVENTORY_MAGICS, 12u,
                      60u + R6_ASSET_INVENTORY_EXTS * 48u, index);
}

int r6_asset_inventory_shader(const void *data, size_t size, uint32_t index,
                              char *path, size_t capacity,
                              uint32_t *file_size, unsigned char *head) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t strings_off;
    int result = asset_rows(data, size, index, 24u,
                            R6_ASSET_INVENTORY_SHADERS,
                            60u + R6_ASSET_INVENTORY_EXTS * 48u +
                                R6_ASSET_INVENTORY_MAGICS * 12u +
                                R6_ASSET_INVENTORY_FOLDERS * 20u,
                            &bytes, &row_off, &strings_off);
    if (result != R6_OK) {
        return result;
    }
    result = asset_name(bytes, size, strings_off,
                        r6_u32(bytes, row_off), path, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (file_size) {
        *file_size = r6_u32(bytes, row_off + 4u);
    }
    if (head) {
        r6_memcpy(head, bytes + row_off + 8u, 16u);
    }
    return R6_OK;
}

int r6_asset_inventory_find_shader(const void *data, size_t size,
                                   const char *path, uint32_t *index) {
    const unsigned char *bytes;
    uint32_t strings_off;
    uint32_t row_off;
    uint32_t at;
    size_t wanted;
    if (!path) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(path);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < R6_ASSET_INVENTORY_SHADERS; at++) {
        char found[R6_ASSET_INVENTORY_NAME_CAP];
        int result = asset_rows(data, size, at, 24u,
                                R6_ASSET_INVENTORY_SHADERS,
                                60u + R6_ASSET_INVENTORY_EXTS * 48u +
                                    R6_ASSET_INVENTORY_MAGICS * 12u +
                                    R6_ASSET_INVENTORY_FOLDERS * 20u,
                                &bytes, &row_off, &strings_off);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        result = asset_name(bytes, size, strings_off,
                            r6_u32(bytes, row_off), found, sizeof(found));
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(found) == wanted &&
            r6_memcmp(found, path, wanted) == 0) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}
