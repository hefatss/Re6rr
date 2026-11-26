package com.wmmt.re6rr;

/** Eight scene slots from one shipped Environment.Lua text file. */
public final class EnvironmentLua {
    private EnvironmentLua() {
    }

    /** stage, stageRoot, stageDay, camId, actor0..actor3. */
    public static long[] parse(byte[] raw) {
        return nativeParse(raw);
    }

    private static native long[] nativeParse(byte[] raw);
}
