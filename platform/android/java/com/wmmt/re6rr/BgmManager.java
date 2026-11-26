package com.wmmt.re6rr;

/** Shipped SoundManager::playBGM id dispatch and stream handle state. */
public final class BgmManager {
    private BgmManager() {
    }

    public static final int CURRENT_OFFSET = 0x44C;
    public static final int NEXT_OFFSET = 0x450;
    public static final int NO_CHANGE = -1;
    public static final int NO_SOUND = 0x8C;
    public static final int RANDOM = 0x8D;

    public static final int ACTION_NONE = 0;
    public static final int ACTION_PLAY = 1;
    public static final int ACTION_FADE = 2;
    public static final int ACTION_QUEUE = 3;
    public static final int ACTION_ALREADY = 4;
    public static final int ACTION_REJECTED = 5;

    /** current, next. */
    public static long[] read(byte[] data) {
        return nativeRead(data);
    }

    /** action, current, next; the data array is updated in place. */
    public static long[] select(byte[] data, int id) {
        return nativeSelect(data, id);
    }

    private static native long[] nativeRead(byte[] data);

    private static native long[] nativeSelect(byte[] data, int id);
}
