// Quick memory-read sanity probe.
// @category Recon

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class ProbeMemory extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (long off : new long[]{0x1000L, 0x8555L, 0x10000L, 0x1d7bbL, 0x20000L,
                                   0x6eef20L, 0xc566f0L, 0x100000L}) {
            Address a = currentProgram.getAddressFactory().getAddress(
                    Long.toHexString(currentProgram.getImageBase().getOffset() + off));
            String v = "?";
            try {
                v = String.format("%02x", currentProgram.getMemory().getByte(a) & 0xff);
            } catch (Exception e) {
                v = "ERR " + e.getMessage();
            }
            println(String.format("%08x -> %s", off, v));
        }
    }
}
