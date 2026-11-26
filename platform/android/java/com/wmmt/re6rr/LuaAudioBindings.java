package com.wmmt.re6rr;

/** Shipped Lua sound bindings recovered from the executable luaL_Reg table. */
public final class LuaAudioBindings {
    private LuaAudioBindings() {
    }

    public static final long NO_ARGUMENT = -1;

    public static int count() {
        return nativeCount();
    }

    /** Lua name, native call. */
    public static String[] names(int index) {
        return nativeNames(index);
    }

    /** function address, bank, tone; -1 marks a Lua argument. */
    public static long[] numbers(int index) {
        return nativeNumbers(index);
    }

    /** Binding index for a Lua name, or -1. */
    public static int find(String name) {
        return nativeFind(name);
    }

    private static native int nativeCount();

    private static native String[] nativeNames(int index);

    private static native long[] nativeNumbers(int index);

    private static native int nativeFind(String name);
}
