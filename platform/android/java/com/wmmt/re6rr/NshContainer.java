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

    /** tag, offset, size and data offset of the first matching chunk;
     *  null for a bad record or absent tag. */
    public static long[] chunkFind(byte[] raw, int record, int tag) {
        return nativeChunkFind(raw, record, tag);
    }

    /** 30 values: record count and the 29 summed DX10 STAT fields across the
     *  446 shipped DXBC records; unknown_* fields stay uninterpretable. */
    public static long[] statFacts() {
        return nativeStatFacts();
    }

    /** 23 values: record/stage counts, target/flags, cbuffer/variable/resource
     *  totals, class/type histograms, nonzero member offsets and dimension /
     *  sample-count codes summed from the 446 shipped RDEF chunks. */
    public static long[] reflectionFacts() {
        return nativeReflectionFacts();
    }

    /** The single shipped RDEF creator string. */
    public static String reflectionCreator() {
        return nativeReflectionCreator();
    }

    /** 7 values: instruction/declaration operand totals, neg/abs/immediate
     *  operands and TestNonZero/Saturate instructions across the 446 SHDRs. */
    public static long[] operandFacts() {
        return nativeOperandFacts();
    }

    private static native long[] nativeParse(byte[] raw);

    private static native long[] nativeChunkFind(byte[] raw, int record,
                                                 int tag);

    private static native long[] nativeStatFacts();

    private static native long[] nativeReflectionFacts();

    private static native String nativeReflectionCreator();

    private static native long[] nativeOperandFacts();
}
