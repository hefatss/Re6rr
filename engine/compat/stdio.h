/* Minimal stdio.h for the freestanding host build of the engine core.
 * Lua's headers include stdio.h but the core does not use FILE streams.
 * The Android build uses the real libc header instead. */
#ifndef R6_COMPAT_STDIO_H
#define R6_COMPAT_STDIO_H

#include <stddef.h>

typedef struct r6_compat_FILE FILE;

/* luaL_Buffer sizes itself with BUFSIZ. The core never touches the CRT. */
#define BUFSIZ 8192
#define EOF (-1)

#endif
