package com.wmmt.re6rr;

/** Bounded NSXR container and DXBC chunk table reader. */
public final class NshContainer {
    private NshContainer() {
    }

    public static final int HEADER_SIZE = 0x80;
    public static final int RECORD_MAX = 2;
    public static final int CHUNK_MAX = 8;

    /** 98 longs: fileSize, version, subversion, flags, recordCount, table[5],
     *  then two 44-value records: offset, count, dxbcSize, reserved,
     *  dxbcOffset, dxbcVersion, dxbcActualSize, chunkCount, digest[4],
     *  chunks[8] as tag/offset/size/dataOffset. Null on malformed bytes. */
    public static long[] parse(byte[] raw) {
        return nativeParse(raw);
    }

    private static native long[] nativeParse(byte[] raw);
}
