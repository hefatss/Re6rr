/* Freestanding inventory of the shipped wmn6r.exe base relocation directory.
 * The blob comes from tools/engine/reloc_inventory_catalog.py. It holds
 * copied page/section facts only; no relocation is applied and no executable
 * bytes are read by the core. */
#ifndef R6_RELOC_INVENTORY_H
#define R6_RELOC_INVENTORY_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_RELOC_PAGE_SIZE 0x1000u

typedef struct r6_reloc_header_t {
    uint32_t version;
    uint32_t directory_rva;
    uint32_t directory_size;
    uint32_t section_count;
    uint32_t block_count;
    uint32_t entry_count;
    uint32_t type_counts[16];
} r6_reloc_header_t;

typedef struct r6_reloc_section_t {
    uint32_t rva;
    uint32_t size;
} r6_reloc_section_t;

typedef struct r6_reloc_block_t {
    uint32_t page_rva;
    uint32_t block_size;
    uint32_t entry_first;
    uint32_t entry_count;
    uint32_t section_index;
} r6_reloc_block_t;

typedef struct r6_reloc_entry_t {
    uint32_t offset;
    uint32_t type;
    uint32_t rva;
    uint32_t block_index;
} r6_reloc_entry_t;

R6_API int r6_reloc_inventory_parse(const void *data, size_t size,
                                    r6_reloc_header_t *out);

R6_API int r6_reloc_inventory_section(const void *data, size_t size,
                                      uint32_t index,
                                      r6_reloc_section_t *out);

R6_API int r6_reloc_inventory_block(const void *data, size_t size,
                                    uint32_t index, r6_reloc_block_t *out);

R6_API int r6_reloc_inventory_entry(const void *data, size_t size,
                                    uint32_t index, r6_reloc_entry_t *out);

#ifdef __cplusplus
}
#endif

#endif
