/* Bounded reader for PE and .pdata facts. The host supplies one derived blob;
 * this file never reads, maps or executes the executable itself. */

#include "r6/r6_pe_inventory.h"

#include "core/internal.h"

static const unsigned char pe_inventory_magic[8] = {
    'R', '6', 'P', 'E', 'I', 0, 1, 0
};

enum {
    R6_PE_HEADER_SIZE = 120,
    R6_PE_FUNC_OFF = 120,
    R6_PE_DLL_OFF = R6_PE_FUNC_OFF + R6_PE_INVENTORY_FUNCS * 16u,
    R6_PE_IMPORT_OFF = R6_PE_DLL_OFF + R6_PE_INVENTORY_DLLS * 12u,
    R6_PE_SECTION_OFF = R6_PE_IMPORT_OFF + R6_PE_INVENTORY_IMPORTS * 12u,
    R6_PE_EXPORT_OFF = R6_PE_SECTION_OFF + R6_PE_INVENTORY_SECTIONS * 24u,
    R6_PE_TLS_OFF = R6_PE_EXPORT_OFF + R6_PE_INVENTORY_EXPORTS * 4u,
    R6_PE_DIRECTORY_OFF = R6_PE_TLS_OFF + R6_PE_INVENTORY_TLS * 8u,
    R6_PE_STRINGS_OFF = R6_PE_DIRECTORY_OFF +
                        R6_PE_INVENTORY_DIRECTORIES * 12u
};

static int pe_header(const void *data, size_t size,
                     r6_pe_inventory_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pe_inventory_header header;
    if (!bytes || !out || size < R6_PE_HEADER_SIZE ||
        r6_memcmp(bytes, pe_inventory_magic,
                  sizeof(pe_inventory_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 44) != R6_PE_INVENTORY_DIRECTORIES ||
        r6_u32(bytes, 48) != R6_PE_INVENTORY_FUNCS ||
        r6_u32(bytes, 84) != R6_PE_INVENTORY_DLLS ||
        r6_u32(bytes, 88) != R6_PE_INVENTORY_IMPORTS ||
        r6_u32(bytes, 92) != R6_PE_INVENTORY_EXPORTS ||
        r6_u32(bytes, 96) != R6_PE_INVENTORY_TLS ||
        r6_u32(bytes, 100) != R6_PE_INVENTORY_SECTIONS) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.file_size = r6_u32(bytes, 12);
    header.machine = r6_u32(bytes, 16);
    header.pe_magic = r6_u32(bytes, 20);
    header.timestamp = r6_u32(bytes, 24);
    header.image_base_lo = r6_u32(bytes, 28);
    header.image_base_hi = r6_u32(bytes, 32);
    header.entry_rva = r6_u32(bytes, 36);
    header.size_of_image = r6_u32(bytes, 40);
    header.directory_count = r6_u32(bytes, 44);
    header.pdata_count = r6_u32(bytes, 48);
    header.unique_unwind = r6_u32(bytes, 52);
    header.code_bytes = r6_u32(bytes, 56);
    header.text_bytes = r6_u32(bytes, 60);
    header.leaf = r6_u32(bytes, 64);
    header.chained = r6_u32(bytes, 68);
    header.with_eh = r6_u32(bytes, 72);
    header.reloc_blocks = r6_u32(bytes, 76);
    header.reloc_entries = r6_u32(bytes, 80);
    header.dll_count = r6_u32(bytes, 84);
    header.import_count = r6_u32(bytes, 88);
    header.export_count = r6_u32(bytes, 92);
    header.tls_count = r6_u32(bytes, 96);
    header.section_count = r6_u32(bytes, 100);
    header.strings_size = r6_u32(bytes, 104);
    header.guid_off = r6_u32(bytes, 108);
    header.pdb_age = r6_u32(bytes, 112);
    header.path_off = r6_u32(bytes, 116);
    if (!header.strings_size ||
        (size_t)R6_PE_STRINGS_OFF + header.strings_size != size ||
        header.entry_rva >= header.size_of_image) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int pe_rows(const void *data, size_t size, uint32_t index,
                   uint32_t stride, uint32_t count, uint32_t base,
                   const unsigned char **bytes, uint32_t *row_off) {
    r6_pe_inventory_header header;
    int result = pe_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = base + index * stride;
    if (*row_off + stride > R6_PE_STRINGS_OFF) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int pe_name(const unsigned char *bytes, size_t size, uint32_t offset,
                   char *out, size_t capacity) {
    uint32_t at = offset;
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (offset < R6_PE_STRINGS_OFF || offset >= size) {
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

int r6_pe_inventory_parse(const void *data, size_t size,
                          r6_pe_inventory_header *out) {
    return pe_header(data, size, out);
}

int r6_pe_inventory_func(const void *data, size_t size, uint32_t index,
                         uint32_t *rva, uint32_t *end, uint32_t *length,
                         uint32_t *leaf) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t begin;
    uint32_t finish;
    uint32_t span;
    uint32_t is_leaf;
    int result = pe_rows(data, size, index, 16u, R6_PE_INVENTORY_FUNCS,
                         R6_PE_FUNC_OFF, &bytes, &row_off);
    if (result != R6_OK) {
        return result;
    }
    begin = r6_u32(bytes, row_off);
    finish = r6_u32(bytes, row_off + 4u);
    span = r6_u32(bytes, row_off + 8u);
    is_leaf = r6_u32(bytes, row_off + 12u);
    if (begin >= finish || span != finish - begin ||
        finish > r6_u32(bytes, 40) || is_leaf > 1u) {
        return R6_ERR_FORMAT;
    }
    if (rva) {
        *rva = begin;
    }
    if (end) {
        *end = finish;
    }
    if (length) {
        *length = span;
    }
    if (leaf) {
        *leaf = is_leaf;
    }
    return R6_OK;
}

int r6_pe_inventory_func_find(const void *data, size_t size, uint32_t rva,
                              uint32_t *index) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_pe_inventory_header header;
    uint32_t low = 0;
    uint32_t high;
    int result = pe_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    high = header.pdata_count;
    while (low < high) {
        uint32_t mid = low + (high - low) / 2u;
        uint32_t found = r6_u32(bytes, R6_PE_FUNC_OFF + mid * 16u);
        if (found < rva) {
            low = mid + 1u;
        } else {
            high = mid;
        }
    }
    if (low == header.pdata_count ||
        r6_u32(bytes, R6_PE_FUNC_OFF + low * 16u) != rva) {
        return R6_ERR_NOT_FOUND;
    }
    if (index) {
        *index = low;
    }
    return R6_OK;
}

int r6_pe_inventory_dll(const void *data, size_t size, uint32_t index,
                        char *name, size_t capacity, uint32_t *import_index,
                        uint32_t *count) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t first = 0;
    uint32_t at;
    int result = pe_rows(data, size, index, 12u, R6_PE_INVENTORY_DLLS,
                         R6_PE_DLL_OFF, &bytes, &row_off);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < index; at++) {
        first += r6_u32(bytes, R6_PE_DLL_OFF + at * 12u + 8u);
    }
    if (r6_u32(bytes, row_off + 4u) != first ||
        first + r6_u32(bytes, row_off + 8u) > R6_PE_INVENTORY_IMPORTS) {
        return R6_ERR_FORMAT;
    }
    result = pe_name(bytes, size, r6_u32(bytes, row_off), name, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (import_index) {
        *import_index = first;
    }
    if (count) {
        *count = r6_u32(bytes, row_off + 8u);
    }
    return R6_OK;
}

int r6_pe_inventory_import(const void *data, size_t size, uint32_t index,
                           uint32_t *kind, uint32_t *ordinal, char *name,
                           size_t capacity) {
    const unsigned char *bytes;
    uint32_t row_off;
    uint32_t value;
    int result = pe_rows(data, size, index, 12u, R6_PE_INVENTORY_IMPORTS,
                         R6_PE_IMPORT_OFF, &bytes, &row_off);
    if (result != R6_OK) {
        return result;
    }
    value = r6_u32(bytes, row_off);
    if (value > R6_PE_INVENTORY_IMPORT_ORDINAL) {
        return R6_ERR_FORMAT;
    }
    if (value == R6_PE_INVENTORY_IMPORT_ORDINAL) {
        if (name && capacity) {
            name[0] = 0;
        }
    } else {
        result = pe_name(bytes, size, r6_u32(bytes, row_off + 8u), name,
                         capacity);
        if (result != R6_OK) {
            return result;
        }
    }
    if (kind) {
        *kind = value;
    }
    if (ordinal) {
        *ordinal = value == R6_PE_INVENTORY_IMPORT_ORDINAL ?
                   r6_u32(bytes, row_off + 4u) : 0u;
    }
    return R6_OK;
}

int r6_pe_inventory_section(const void *data, size_t size, uint32_t index,
                            char *name, size_t capacity, uint32_t *vsize,
                            uint32_t *vaddr, uint32_t *raw_size,
                            uint32_t *raw_ptr, uint32_t *characteristics) {
    const unsigned char *bytes;
    uint32_t row_off;
    int result = pe_rows(data, size, index, 24u, R6_PE_INVENTORY_SECTIONS,
                         R6_PE_SECTION_OFF, &bytes, &row_off);
    if (result != R6_OK) {
        return result;
    }
    result = pe_name(bytes, size, r6_u32(bytes, row_off), name, capacity);
    if (result != R6_OK) {
        return result;
    }
    if (vsize) {
        *vsize = r6_u32(bytes, row_off + 4u);
    }
    if (vaddr) {
        *vaddr = r6_u32(bytes, row_off + 8u);
    }
    if (raw_size) {
        *raw_size = r6_u32(bytes, row_off + 12u);
    }
    if (raw_ptr) {
        *raw_ptr = r6_u32(bytes, row_off + 16u);
    }
    if (characteristics) {
        *characteristics = r6_u32(bytes, row_off + 20u);
    }
    return R6_OK;
}

int r6_pe_inventory_export(const void *data, size_t size, uint32_t index,
                           char *name, size_t capacity) {
    const unsigned char *bytes;
    uint32_t row_off;
    int result = pe_rows(data, size, index, 4u, R6_PE_INVENTORY_EXPORTS,
                         R6_PE_EXPORT_OFF, &bytes, &row_off);
    if (result != R6_OK) {
        return result;
    }
    return pe_name(bytes, size, r6_u32(bytes, row_off), name, capacity);
}

int r6_pe_inventory_tls(const void *data, size_t size, uint32_t index,
                        uint32_t *address_lo, uint32_t *address_hi) {
    const unsigned char *bytes;
    uint32_t row_off;
    int result = pe_rows(data, size, index, 8u, R6_PE_INVENTORY_TLS,
                         R6_PE_TLS_OFF, &bytes, &row_off);
    if (result != R6_OK) {
        return result;
    }
    if (r6_u32(bytes, row_off) < r6_u32(bytes, 40)) {
        return R6_ERR_FORMAT;
    }
    if (address_lo) {
        *address_lo = r6_u32(bytes, row_off);
    }
    if (address_hi) {
        *address_hi = r6_u32(bytes, row_off + 4u);
    }
    return R6_OK;
}

int r6_pe_inventory_directory(const void *data, size_t size, uint32_t index,
                              uint32_t *dir_index, uint32_t *rva,
                              uint32_t *dir_size) {
    r6_pe_inventory_header header;
    const unsigned char *bytes;
    uint32_t row_off;
    int result = pe_rows(data, size, index, 12u,
                          R6_PE_INVENTORY_DIRECTORIES, R6_PE_DIRECTORY_OFF,
                          &bytes, &row_off);
    if (result != R6_OK) {
        return result;
    }
    result = pe_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (r6_u32(bytes, row_off) > 15u ||
        r6_u32(bytes, row_off + 4u) >= header.size_of_image ||
        r6_u32(bytes, row_off + 8u) > header.size_of_image) {
        return R6_ERR_FORMAT;
    }
    if (dir_index) {
        *dir_index = r6_u32(bytes, row_off);
    }
    if (rva) {
        *rva = r6_u32(bytes, row_off + 4u);
    }
    if (dir_size) {
        *dir_size = r6_u32(bytes, row_off + 8u);
    }
    return R6_OK;
}

int r6_pe_inventory_directory_find(const void *data, size_t size,
                                   uint32_t dir_index, uint32_t *row_index) {
    uint32_t at;
    r6_pe_inventory_header header;
    int result = pe_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.directory_count; at++) {
        uint32_t found = 0;
        result = r6_pe_inventory_directory(data, size, at, &found, NULL, NULL);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (found == dir_index) {
            if (row_index) {
                *row_index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_pe_inventory_dll_find(const void *data, size_t size,
                             const char *name, uint32_t *index) {
    r6_pe_inventory_header header;
    size_t wanted;
    uint32_t at;
    int result = pe_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!name) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.dll_count; at++) {
        char found[256];
        result = r6_pe_inventory_dll(data, size, at, found, sizeof(found),
                                     NULL, NULL);
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

int r6_pe_inventory_pdb(const void *data, size_t size, char *guid,
                        size_t guid_capacity, uint32_t *age, char *path,
                        size_t path_capacity) {
    r6_pe_inventory_header header;
    const unsigned char *bytes = (const unsigned char *)data;
    int result = pe_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = pe_name(bytes, size, header.guid_off, guid, guid_capacity);
    if (result != R6_OK) {
        return result;
    }
    result = pe_name(bytes, size, header.path_off, path, path_capacity);
    if (result != R6_OK) {
        return result;
    }
    if (age) {
        *age = header.pdb_age;
    }
    return R6_OK;
}

