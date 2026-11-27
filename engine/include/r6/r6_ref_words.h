/* Freestanding reader for reference-word xrefs recovered from wmn6r.exe.
 * The derived blob comes from tools/engine/ref_words_catalog.py. Values are
 * raw low-32 bit operand words, not dereferenced pointers. */
#ifndef R6_REF_WORDS_H
#define R6_REF_WORDS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_REF_WORDS_COUNT = 98805,
    R6_REF_XREFS = 174507
};

typedef struct r6_ref_words_header {
    uint32_t version;
    uint32_t word_count;
    uint32_t xref_count;
} r6_ref_words_header;

R6_API int r6_ref_words_parse(const void *data, size_t size,
                              r6_ref_words_header *out);

R6_API int r6_ref_words_word(const void *data, size_t size, uint32_t index,
                             uint32_t *value, uint32_t *xref_first,
                             uint32_t *xref_count);

R6_API int r6_ref_words_xref(const void *data, size_t size, uint32_t index,
                             uint32_t *rva);

R6_API int r6_ref_words_word_xref(const void *data, size_t size,
                                  uint32_t word_index, uint32_t local_index,
                                  uint32_t *rva);

/* Exact match by raw low-32 bit word. */
R6_API int r6_ref_words_find(const void *data, size_t size, uint32_t value,
                             uint32_t *word_index);

/* All global xref indices with that exact RVA, in stored order. *count receives
 * the total hit count; up to capacity indices are copied. R6_ERR_NOT_FOUND
 * means no row matched; R6_ERR_BUFFER means capacity was short. */
R6_API int r6_ref_words_find_rva(const void *data, size_t size, uint32_t rva,
                                 uint32_t *indices, uint32_t capacity,
                                 uint32_t *count);

#ifdef __cplusplus
}
#endif

#endif
