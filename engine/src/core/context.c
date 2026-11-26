/* Context bundles: the ordered script sets the engine loads per car, colour or
 * course. The executable loads a script immediately after compiling it
 * (LuabindPack::Load at FUN_140aac140 calls luaL_loadbuffer then
 * FUN_140aad540 to run it), so ordering here is load ordering. */

#include "r6/r6_context.h"

#include "internal.h"

static int ctx_name_ok(const char *value) {
    size_t at;
    size_t length;
    if (!value) {
        return 0;
    }
    length = r6_strlen(value);
    if (!length || length > 0x80u) {
        return 0;
    }
    for (at = 0; at < length; at++) {
        unsigned char c = (unsigned char)value[at];
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
              (c >= '0' && c <= '9') || c == '_')) {
            return 0;
        }
    }
    return 1;
}

static int ctx_append(char *out, size_t *used, size_t capacity,
                      const char *text) {
    size_t length = r6_strlen(text);
    if (*used + length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out + *used, text, length);
    *used += length;
    out[*used] = 0;
    return R6_OK;
}

int r6_context_path(int set, int index, const char *car, const char *model,
                    char *out, size_t capacity) {
    const char *prefix;
    const char *suffix;
    const char *name;
    size_t used = 0;
    int result;
    if (!out || !capacity || !ctx_name_ok(car) || !ctx_name_ok(model)) {
        return R6_ERR_ARG;
    }
    prefix = NULL;
    suffix = NULL;
    name = NULL;
    switch (set) {
    case R6_CONTEXT_TIRE:
        if (index == 0) {
            prefix = "data/car/tire/script/TireDefine.lua";
        } else if (index == 1) {
            prefix = "data/car/tire/model_type/TireModelType_";
            suffix = ".lua";
            name = car;
        } else if (index == 2) {
            prefix = "data/car/tire/script/TireAccessor.lua";
        }
        break;
    case R6_CONTEXT_POSITION:
        if (index == 0) {
            prefix = "data/car/position/pos/getTirePos_";
            suffix = ".lua";
            name = car;
        } else if (index == 1) {
            prefix = "data/car/position/hightDown/CarHightDown_";
            suffix = ".lua";
            name = model;
        } else if (index == 2) {
            prefix = "data/car/position/StroboLightOnOffParameter.lua";
        }
        break;
    case R6_CONTEXT_SHADER:
        if (index == 0) {
            prefix = "data/car/shader/parameter/";
            suffix = "_ShaderParameter.lua";
            name = model;
        } else if (index == 1) {
            prefix = "data/car/shader/script/ShaderAccessor.lua";
        }
        break;
    case R6_CONTEXT_SPECIFICATION:
        if (index == 0) {
            prefix = "data/car/specification/";
            suffix = "_Specification.lua";
            name = model;
        }
        break;
    case R6_CONTEXT_COLOR:
        if (index == 0) {
            prefix = "data/car/color/LibraryColor.lua";
        } else if (index == 1) {
            prefix = "data/car/color/ColorCommonParamerter.lua";
        } else if (index == 2) {
            prefix = "data/car/color/NeonColor.lua";
        }
        break;
    default:
        break;
    }
    if (!prefix) {
        return R6_ERR_NOT_FOUND;
    }
    result = ctx_append(out, &used, capacity, prefix);
    if (result == R6_OK && name) {
        result = ctx_append(out, &used, capacity, name);
    }
    if (result == R6_OK && suffix) {
        result = ctx_append(out, &used, capacity, suffix);
    }
    return result;
}

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
