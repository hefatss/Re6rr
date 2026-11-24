/* Minimal string.h for freestanding miniz builds.
 * miniz_config.h maps the byte helpers to the core's own implementations.
 */
#ifndef R6_MINIZ_COMPAT_STRING_H
#define R6_MINIZ_COMPAT_STRING_H
#include <stddef.h>
void *memcpy(void *dst, const void *src, size_t size);
void *memset(void *dst, int value, size_t size);
int memcmp(const void *a, const void *b, size_t size);
#endif
