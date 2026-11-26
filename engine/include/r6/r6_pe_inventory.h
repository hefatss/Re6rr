/* Freestanding reader for PE and .pdata facts derived from the shipped
 * wmn6r.exe. The derived blob comes from tools/engine/pe_inventory_catalog.py.
 * No PE bytes are read, mapped or executed by the core. */
#ifndef R6_PE_INVENTORY_H
#define R6_PE_INVENTORY_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_PE_INVENTORY_FUNCS = 70377,
    R6_PE_INVENTORY_DLLS = 28,
    R6_PE_INVENTORY_IMPORTS = 825,
    R6_PE_INVENTORY_EXPORTS = 2,
    R6_PE_INVENTORY_TLS = 1,
    R6_PE_INVENTORY_SECTIONS = 7,
    R6_PE_INVENTORY_IMPORT_NAME = 0,
    R6_PE_INVENTORY_IMPORT_ORDINAL = 1
};

typedef struct r6_pe_inventory_header {
    uint32_t version;
    uint32_t file_size;
    uint32_t machine;
    uint32_t pe_magic;
    uint32_t timestamp;
    uint32_t image_base_lo;
    uint32_t image_base_hi;
    uint32_t entry_rva;
    uint32_t size_of_image;
    uint32_t directory_count;
    uint32_t pdata_count;
    uint32_t unique_unwind;
    uint32_t code_bytes;
    uint32_t text_bytes;
    uint32_t leaf;
    uint32_t chained;
    uint32_t with_eh;
    uint32_t reloc_blocks;
    uint32_t reloc_entries;
    uint32_t dll_count;
    uint32_t import_count;
    uint32_t export_count;
    uint32_t tls_count;
    uint32_t section_count;
    uint32_t strings_size;
    uint32_t guid_off;
    uint32_t pdb_age;
    uint32_t path_off;
} r6_pe_inventory_header;

R6_API int r6_pe_inventory_parse(const void *data, size_t size,
                                 r6_pe_inventory_header *out);

R6_API int r6_pe_inventory_func(const void *data, size_t size,
                                uint32_t index, uint32_t *rva, uint32_t *end,
                                uint32_t *length, uint32_t *leaf);

R6_API int r6_pe_inventory_dll(const void *data, size_t size, uint32_t index,
                               char *name, size_t capacity,
                               uint32_t *import_index, uint32_t *count);

R6_API int r6_pe_inventory_import(const void *data, size_t size,
                                  uint32_t index, uint32_t *kind,
                                  uint32_t *ordinal, char *name,
                                  size_t capacity);

R6_API int r6_pe_inventory_section(const void *data, size_t size,
                                   uint32_t index, char *name,
                                   size_t capacity, uint32_t *vsize,
                                   uint32_t *vaddr, uint32_t *raw_size,
                                   uint32_t *raw_ptr,
                                   uint32_t *characteristics);

R6_API int r6_pe_inventory_export(const void *data, size_t size,
                                  uint32_t index, char *name,
                                  size_t capacity);

R6_API int r6_pe_inventory_tls(const void *data, size_t size, uint32_t index,
                               uint32_t *address_lo, uint32_t *address_hi);

R6_API int r6_pe_inventory_pdb(const void *data, size_t size, char *guid,
                               size_t guid_capacity, uint32_t *age,
                               char *path, size_t path_capacity);

#ifdef __cplusplus
}
#endif

#endif
