// Probe address/function lookup for the recon workflow.
// @category Recon

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

public class ProbeFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("imageBase = " + currentProgram.getImageBase());
        println("numFunctions = " + currentProgram.getFunctionManager().getFunctionCount());
        String[] tests = {"0x140008555", "ram:140008555", "0x8555",
                          "0x140001d7bb", "0x1400c566f0", "0x1400c56400",
                          "0x14006eef20", "0x1400c58590", "0x1400584f60"};
        for (String s : tests) {
            Address a = currentProgram.getAddressFactory().getAddress(s);
            String bytes = "?";
            if (a != null) {
                try {
                    byte[] b = new byte[8];
                    int got = currentProgram.getMemory().getBytes(a, b);
                    StringBuilder sb = new StringBuilder();
                    for (int j = 0; j < got; j++) sb.append(String.format("%02x", b[j]));
                    bytes = sb.toString();
                } catch (Exception e) {
                    bytes = "ERR " + e.getMessage();
                }
            }
            println(s + " -> " + a + " bytes=" + bytes + " exact=" +
                    (a == null ? "null" : String.valueOf(currentProgram.getFunctionManager().getFunctionAt(a))) +
                    " containing=" +
                    (a == null ? "null" : String.valueOf(currentProgram.getFunctionManager().getFunctionContaining(a))));
        }
        for (ghidra.program.model.mem.MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            println("block " + b.getName() + " " + b.getStart() + "-" + b.getEnd() + " init=" + b.isInitialized());
        }
        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
        for (int i = 0; i < 5 && it.hasNext(); i++) {
            Function f = it.next();
            println("sample " + f.getEntryPoint() + " " + f.getName());
        }
    }
}
