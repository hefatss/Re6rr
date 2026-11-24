/* Context bundles: the ordered script sets the engine loads per car, colour or
 * course. The executable loads a script immediately after compiling it
 * (LuabindPack::Load at FUN_140aac140 calls luaL_loadbuffer then
 * FUN_140aad540 to run it), so ordering here is load ordering. */

#include "internal.h"

int r6_engine_load_context(r6_engine *engine,
                           const r6_script_source *scripts, size_t count) {
    size_t i;
    if (!engine || !engine->L || (count && !scripts)) {
        return R6_ERR_ARG;
    }
    for (i = 0; i < count; i++) {
        const r6_script_source *script = &scripts[i];
        int rc;
        if (!script->data || script->size == 0) {
            r6_set_error(engine, "context script without bytes");
            return R6_ERR_ARG;
        }
        rc = r6_engine_load_script(engine, script->name, script->data,
                                   script->size);
        if (rc != R6_OK) {
            return rc;
        }
    }
    return R6_OK;
}
