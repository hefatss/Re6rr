// Probe instruction decode at .pdata entries Ghidra skipped.
// @category Recon

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;

public class ProbeDecode extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] tests = {"0x140001d7bb", "0x1400c566f0", "0x14006eef20", "0x140008555"};
        for (String s : tests) {
            Address a = currentProgram.getAddressFactory().getAddress(s);
            println(s + " before=" + String.valueOf(getInstructionAt(a)));
            boolean ok = disassemble(a);
            Instruction ins = getInstructionAt(a);
            println(s + " disassemble=" + ok + " ins=" + String.valueOf(ins));
        }
    }
}
