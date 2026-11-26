package com.wmmt.re6rr;

/** PE header, .pdata, import, section, directory, export and TLS facts from wmn6r.exe.
 *  No executable bytes are copied: the blob holds counts, RVAs and names. */
public final class PeInventory {
    private PeInventory() {
    }

    /** Header values in packed order: version, file size, machine, magic,
     * timestamp, image base low/high, entry RVA, image size, directory count,
     * .pdata count, unique unwind count, code/text bytes, leaf/chained/EH
     * counts, relocation blocks/entries, DLL/import/export/TLS/section counts,
     * strings size, PDB GUID offset, PDB age and PDB path offset. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** rva, end, size and leaf flag for one .pdata row. */
    public static long[] func(byte[] blob, int index) {
        return nativeFunc(blob, index);
    }

    public static String dllName(byte[] blob, int index) {
        return nativeDllName(blob, index);
    }

    /** First global import index and import count for one DLL. */
    public static long[] dllRange(byte[] blob, int index) {
        return nativeDllRange(blob, index);
    }

    /** Import kind (0 = name, 1 = ordinal) and ordinal value. */
    public static long[] imp(byte[] blob, int index) {
        return nativeImp(blob, index);
    }

    public static String importName(byte[] blob, int index) {
        return nativeImportName(blob, index);
    }

    public static String sectionName(byte[] blob, int index) {
        return nativeSectionName(blob, index);
    }

    /** vsize, vaddr, raw size, raw pointer and characteristics. */
    public static long[] section(byte[] blob, int index) {
        return nativeSection(blob, index);
    }

    public static String exportName(byte[] blob, int index) {
        return nativeExportName(blob, index);
    }

    /** TLS callback address, low and high 32 bits. */
    public static long[] tls(byte[] blob, int index) {
        return nativeTls(blob, index);
    }

    /** PE directory index, RVA and size. */
    public static long[] directory(byte[] blob, int index) {
        return nativeDirectory(blob, index);
    }

    public static String pdbGuid(byte[] blob) {
        return nativePdbGuid(blob);
    }

    public static long pdbAge(byte[] blob) {
        return nativePdbAge(blob);
    }

    public static String pdbPath(byte[] blob) {
        return nativePdbPath(blob);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFunc(byte[] blob, int index);

    private static native String nativeDllName(byte[] blob, int index);

    private static native long[] nativeDllRange(byte[] blob, int index);

    private static native long[] nativeImp(byte[] blob, int index);

    private static native String nativeImportName(byte[] blob, int index);

    private static native String nativeSectionName(byte[] blob, int index);

    private static native long[] nativeSection(byte[] blob, int index);

    private static native String nativeExportName(byte[] blob, int index);

    private static native long[] nativeTls(byte[] blob, int index);

    private static native long[] nativeDirectory(byte[] blob, int index);

    private static native String nativePdbGuid(byte[] blob);

    private static native long nativePdbAge(byte[] blob);

    private static native String nativePdbPath(byte[] blob);
}
