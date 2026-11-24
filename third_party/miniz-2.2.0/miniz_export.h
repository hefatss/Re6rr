/* Export/allocation shim for the vendored single-file miniz 2.2.0.
 *
 * Upstream's amalgamation expects a generated miniz_export.h. We pin the
 * export macro to nothing and disable heap allocation: the inflate wrapper in
 * engine/src/assets/inflate.c supplies its own zalloc/zfree callbacks.
 */
#ifndef MINIZ_EXPORT_H
#define MINIZ_EXPORT_H

#ifndef MINIZ_EXPORT
#define MINIZ_EXPORT
#endif

#ifdef MINIZ_NO_MALLOC
/* miniz_common.h defines MZ_MALLOC/MZ_FREE/MZ_REALLOC under this flag. */
#else
#include <stdlib.h>
#define MZ_MALLOC(x) malloc(x)
#define MZ_FREE(x) free(x)
#define MZ_REALLOC(p, x) realloc((p), (x))
#endif

#endif
