package com.wmmt.re6rr;

/** Shipped asset-tree counts, magic rows, folders and shader samples. */
public final class AssetInventory {
    private AssetInventory() {
    }

    /** root count, classified[2], ext[2], magic[2], folder[2], shader count,
     * strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** root, files, bytes and seven inner-kind counts. */
    public static long[] ext(byte[] blob, int index) {
        return nativeExt(blob, index);
    }

    /** root and file count for one inner magic. */
    public static long[] magic(byte[] blob, int index) {
        return nativeMagic(blob, index);
    }

    /** root, files and bytes for one top folder. */
    public static long[] folder(byte[] blob, int index) {
        return nativeFolder(blob, index);
    }

    /** Shader sample size; path and 16-byte head have separate accessors. */
    public static long shaderSize(byte[] blob, int index) {
        return nativeShaderSize(blob, index);
    }

    public static String extName(byte[] blob, int index) {
        return nativeExtName(blob, index);
    }

    public static String magicName(byte[] blob, int index) {
        return nativeMagicName(blob, index);
    }

    public static String folderName(byte[] blob, int index) {
        return nativeFolderName(blob, index);
    }

    /** row index for an exact extension or folder name; -1 if absent. */
    public static long findExt(byte[] blob, String name) {
        return nativeFindExt(blob, name);
    }

    public static long findFolder(byte[] blob, String name) {
        return nativeFindFolder(blob, name);
    }

    public static long findMagic(byte[] blob, String name) {
        return nativeFindMagic(blob, name);
    }

    public static String shaderPath(byte[] blob, int index) {
        return nativeShaderPath(blob, index);
    }

    public static byte[] shaderHead(byte[] blob, int index) {
        return nativeShaderHead(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeExt(byte[] blob, int index);

    private static native long[] nativeMagic(byte[] blob, int index);

    private static native long[] nativeFolder(byte[] blob, int index);

    private static native long nativeShaderSize(byte[] blob, int index);

    private static native String nativeExtName(byte[] blob, int index);

    private static native String nativeMagicName(byte[] blob, int index);

    private static native String nativeFolderName(byte[] blob, int index);

    private static native long nativeFindExt(byte[] blob, String name);

    private static native long nativeFindFolder(byte[] blob, String name);

    private static native long nativeFindMagic(byte[] blob, String name);

    private static native String nativeShaderPath(byte[] blob, int index);

    private static native byte[] nativeShaderHead(byte[] blob, int index);
}
