/* Freestanding reader for raw shipped string xrefs from wmn6r.exe. The
 * derived blob comes from tools/engine/string_xrefs_catalog.py. RVAs are
 * copied as numbers; no executable bytes are read or mapped. */
#ifndef R6_STRING_XREFS_H
#define R6_STRING_XREFS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_STRING_XREF_NAMES = 195,
    R6_STRING_XREF_RVAS = 222,
    R6_STRING_XREF_NAME_CAP = 256
};

typedef struct r6_string_xref_header {
    uint32_t version;
    uint32_t instructions;
    uint32_t string_refs;
    uint32_t strings;
    uint32_t names_requested;
    uint32_t names_found;
    uint32_t name_count;
    uint32_t rva_count;
    uint32_t strings_size;
    uint32_t strings_off;
} r6_string_xref_header;

R6_API int r6_string_xref_parse(const void *data, size_t size,
                                r6_string_xref_header *out);

R6_API int r6_string_xref_name(const void *data, size_t size, uint32_t index,
                               char *name, size_t capacity,
                               uint32_t *rva_first, uint32_t *rva_count);

R6_API int r6_string_xref_rva(const void *data, size_t size, uint32_t index,
                              uint32_t *rva);

R6_API int r6_string_xref_name_rva(const void *data, size_t size,
                                   uint32_t name_index, uint32_t local_index,
                                   uint32_t *rva);

/* First exact name match; R6_ERR_NOT_FOUND means no hit. */
R6_API int r6_string_xref_find(const void *data, size_t size,
                               const char *name, uint32_t *index);

#ifdef __cplusplus
}
#endif

#endif
