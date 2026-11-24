/* Compile-time shim for the vendored miniz in the freestanding engine build.
 * Included with -include, before miniz.h, for both the host DLL and Android.
 */
#ifndef R6_MINIZ_CONFIG_H
#define R6_MINIZ_CONFIG_H

#include <stddef.h>

#define MINIZ_NO_STDIO 1
#define MINIZ_NO_TIME 1
#define MINIZ_NO_DEFLATE_APIS 1
#define MINIZ_NO_ARCHIVE_APIS 1
#define MINIZ_NO_MALLOC 1

/* The freestanding host has no CRT; use the core's own byte helpers. */
void *r6_memcpy(void *dst, const void *src, size_t size);
void *r6_memset(void *dst, int value, size_t size);
int r6_memcmp(const void *a, const void *b, size_t size);
#define memcpy r6_memcpy
#define memset r6_memset
#define memcmp r6_memcmp

#endif
