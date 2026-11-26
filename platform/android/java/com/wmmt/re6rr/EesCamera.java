package com.wmmt.re6rr;

/** Named camera_data fields recovered from the shipped EES debug logger. */
public final class EesCamera {
    private EesCamera() {
    }

    public static final int STRIDE = 0x160;
    public static final String[] NAMES = {
        "m_CamType", "m_StratFrame", "m_ActFrame", "m_WiatMode",
        "m_StratFieldAngle", "m_EndFieldAngle", "m_FieldAngleCalcId",
        "m_GlobalLookAt", "m_LookAtId", "m_LookAtStartRenge",
        "m_LookAtStartCamRotX", "m_LookAtStartCamRotY",
        "m_LookAtStartCamRotZ", "m_LookAtEndRenge", "m_LookAtEndCamRotX",
        "m_LookAtEndCamRotY", "m_LookAtEndCamRotZ", "m_TransCalcId",
        "m_RotCalcId", "m_StratOpRotZ", "m_EndOpRotZ", "m_OpRotZCalcId",
        "m_LookAtStartOfsetPosX", "m_LookAtStartOfsetPosY",
        "m_LookAtStartOfsetPosZ", "m_LookAtEndOfsetPosX",
        "m_LookAtEndOfsetPosY", "m_LookAtEndOfsetPosZ", "m_OfsetCalcId",
        "m_StartConnection", "m_EndConnection"
    };

    /** 31 values in NAMES order, or null for invalid bytes or offset. */
    public static double[] fields(byte[] raw, int offset) {
        return nativeFields(raw, offset);
    }

    /** Last non-empty record covering a frame, or -1; -1 also on bad input. */
    public static int atFrame(byte[] raw, int offset, int count, int frame) {
        return nativeAtFrame(raw, offset, count, frame);
    }

    private static native double[] nativeFields(byte[] raw, int offset);

    private static native int nativeAtFrame(byte[] raw, int offset, int count,
                                            int frame);
}
