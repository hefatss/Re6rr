package com.wmmt.re6rr;

import java.util.Arrays;

/** EMTIS section bounds, head tokens and prefix name counts. */
public final class EmtisTable {
    private EmtisTable() {
    }

    /** 258 doubles: versionCount, version[8], headerCount, header[64],
     *  tokenCount, sectionCount, sections[16] as marker/start/length/head[8],
     *  nameCount and Missfire/Turbin/Intake/Engine counts. Null on bad input. */
    public static double[] parse(byte[] raw) {
        return nativeParse(raw);
    }

    public static double[] sections(double[] parsed) {
        if (parsed == null) {
            return null;
        }
        int count = (int)parsed[75];
        return Arrays.copyOfRange(parsed, 76, 76 + count * 11);
    }

    public static double[] nameCounts(double[] parsed) {
        return parsed == null ? null : Arrays.copyOfRange(parsed, 253, 257);
    }

    private static native double[] nativeParse(byte[] raw);
}
