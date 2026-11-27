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
     * strings size, PDB GUID offset, PDB age, PDB path offset, pdata RVAs and
     * entry size, symbol table/count, debug type count/value, SHA-256 offset
     * and exe path offset. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Copied SHA-256 of the shipped executable; null on bad input. */
    public static String sha256(byte[] blob) {
        return nativeSha256(blob);
    }

    /** Copied source executable path; null on bad input. */
    public static String exePath(byte[] blob) {
        return nativeExePath(blob);
    }

    /** rva, end, size and leaf flag for one .pdata row. */
    public static long[] func(byte[] blob, int index) {
        return nativeFunc(blob, index);
    }

    /** row index for an exact function RVA; -1 if absent. */
    public static long funcFind(byte[] blob, long rva) {
        if (rva < 0 || rva > 0xFFFFFFFFL) {
            return -1;
        }
        return nativeFuncFind(blob, rva);
    }

    /** row index whose [begin, end) range covers the RVA; -1 if none. */
    public static long funcCover(byte[] blob, long rva) {
        if (rva < 0 || rva > 0xFFFFFFFFL) {
            return -1;
        }
        return nativeFuncCover(blob, rva);
    }

    /** row index for an exact DLL name; -1 if absent. */
    public static long dllFind(byte[] blob, String name) {
        return nativeDllFind(blob, name);
    }

    public static String dllName(byte[] blob, int index) {
        return nativeDllName(blob, index);
    }

    /** First global import index and import count for one DLL. */
    public static long[] dllRange(byte[] blob, int index) {
        return nativeDllRange(blob, index);
    }

    /** first named import row in one DLL range; -1 if absent. */
    public static long importFind(byte[] blob, int dllIndex, String name) {
        return nativeImportFind(blob, dllIndex, name);
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

    /** row index for a PE directory index; -1 if absent. */
    public static long directoryFind(byte[] blob, int dirIndex) {
        return nativeDirectoryFind(blob, dirIndex);
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

    private static native String nativeSha256(byte[] blob);

    private static native String nativeExePath(byte[] blob);

    private static native long[] nativeFunc(byte[] blob, int index);

    private static native long nativeFuncFind(byte[] blob, long rva);

    private static native long nativeFuncCover(byte[] blob, long rva);

    private static native String nativeDllName(byte[] blob, int index);

    private static native long nativeDllFind(byte[] blob, String name);

    private static native long[] nativeDllRange(byte[] blob, int index);

    private static native long[] nativeImp(byte[] blob, int index);

    private static native String nativeImportName(byte[] blob, int index);

    private static native long nativeImportFind(byte[] blob, int dllIndex,
                                                String name);

    private static native String nativeSectionName(byte[] blob, int index);

    private static native long[] nativeSection(byte[] blob, int index);

    private static native String nativeExportName(byte[] blob, int index);

    private static native long[] nativeTls(byte[] blob, int index);

    private static native long[] nativeDirectory(byte[] blob, int index);

    private static native long nativeDirectoryFind(byte[] blob, int dirIndex);

    private static native String nativePdbGuid(byte[] blob);

    private static native long nativePdbAge(byte[] blob);

    private static native String nativePdbPath(byte[] blob);
}
