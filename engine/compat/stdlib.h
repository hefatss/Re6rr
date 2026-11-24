/* Minimal stdlib.h for syntax-checking the JNI layer without a Windows SDK.
 * The Android build uses the real libc header. */
#ifndef R6_COMPAT_STDLIB_H
#define R6_COMPAT_STDLIB_H
#include <stddef.h>
#ifndef NULL
#define NULL ((void *)0)
#endif
void *malloc(size_t size);
void *calloc(size_t count, size_t size);
void free(void *ptr);
#endif
