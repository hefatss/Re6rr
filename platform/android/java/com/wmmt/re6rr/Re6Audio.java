package com.wmmt.re6rr;

/** Read-only nuSound2 .nub bank view for host-side playback preparation. */
public final class Re6Audio {
    private Re6Audio() {
    }

    /** bank id, tone count, header size, data size, first record. */
    public static int[] header(byte[] data) {
        return nativeHeader(data);
    }

    /** index, slot, group, record_offset, length, data_offset, flags,
     *  format_count, rate, channels, bits, loop_flag, three_d_param_no,
     *  format_tag, format_channels, block_align, byte_rate. */
    public static int[] tone(byte[] data, int index) {
        return nativeTone(data, index);
    }

    /** volume, three_d_float_a, three_d_float_b, three_d_param_no,
     *  volume_cap, pan_cap, bus_id, voice_bus. */
    public static double[] control(byte[] data, int index) {
        return nativeControl(data, index);
    }

    /** PCM bytes for one tone, or null on error. */
    public static byte[] pcm(byte[] data, int index) {
        return nativePcm(data, index);
    }

    private static native int[] nativeHeader(byte[] data);
    private static native int[] nativeTone(byte[] data, int index);
    private static native double[] nativeControl(byte[] data, int index);
    private static native byte[] nativePcm(byte[] data, int index);
}
