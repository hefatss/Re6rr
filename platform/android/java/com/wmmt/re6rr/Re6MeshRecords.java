package com.wmmt.re6rr;

/** Bounded, read-only view of raw NDWD subrecords and chain records.
 *
 * Input is one inflated NDWD stream, not the enclosing XMD container. Tokens
 * and names are copied verbatim; no material or texture meaning is inferred.
 */
public final class Re6MeshRecords {
    private Re6MeshRecords() {
    }

    /** id, version, group count, section sizes[0..3]; null on error. */
    public static long[] header(byte[] stream) {
        return nativeHeader(stream);
    }

    /** offset, name offset, subrecord count, subrecord start; null on error. */
    public static long[] group(byte[] stream, int index) {
        return nativeGroup(stream, index);
    }

    /** offset, tokens[0..3], extra, chain offset; null on error. */
    public static long[] subrecord(byte[] stream, int groupIndex, int subIndex) {
        return nativeSubrecord(stream, groupIndex, subIndex);
    }

    /** offset, stride, name offset, flag of one raw chain record; null on error. */
    public static long[] chainRecord(byte[] stream, int groupIndex,
                                     int subIndex, int recordIndex) {
        return nativeChainRecord(stream, groupIndex, subIndex, recordIndex);
    }

    /** NUL-terminated string at 0x30 + sum(section sizes) + offset. */
    public static String name(byte[] stream, int offset) {
        return nativeName(stream, offset);
    }

    private static native long[] nativeHeader(byte[] stream);
    private static native long[] nativeGroup(byte[] stream, int index);
    private static native long[] nativeSubrecord(byte[] stream, int groupIndex,
                                                 int subIndex);
    private static native long[] nativeChainRecord(byte[] stream,
                                                   int groupIndex,
                                                   int subIndex,
                                                   int recordIndex);
    private static native String nativeName(byte[] stream, int offset);
}
