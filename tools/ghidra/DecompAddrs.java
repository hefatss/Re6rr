// Decompile functions at explicit addresses and list their direct callers.
//
//   analyzeHeadless <proj> wmn6r -process wmn6r.exe -noanalysis \
//       -scriptPath <this dir> -postScript DecompAddrs.java <out dir> 0xADDR...
// @category Recon

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.util.task.ConsoleTaskMonitor;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

public class DecompAddrs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("usage: DecompAddrs.java <out dir> <addr>...");
            return;
        }
        String outDir = args[0];
        Files.createDirectories(Paths.get(outDir));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        ConsoleTaskMonitor monitor = new ConsoleTaskMonitor();

        for (int i = 1; i < args.length; i++) {
            Address at = currentProgram.getAddressFactory().getAddress(args[i]);
            Function f = currentProgram.getFunctionManager().getFunctionAt(at);
            if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(at);
            if (f == null) {
                println("NO FUNCTION " + args[i]);
                continue;
            }
            println("=== " + f.getName() + " @" + f.getEntryPoint() + " size " + f.getBody().getNumAddresses());
            for (Reference r : getReferencesTo(f.getEntryPoint())) {
                Function caller = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
                println("  caller " + r.getFromAddress() + " " + (caller == null ? "?" : caller.getName()));
            }
            try {
                DecompileResults res = di.decompileFunction(f, 120, monitor);
                if (!res.decompileCompleted()) {
                    println("FAILED: " + res.getErrorMessage());
                    continue;
                }
                String c = res.getDecompiledFunction().getC();
                String label = "func_" + f.getEntryPoint().toString().replace(":", "_");
                Files.write(Paths.get(outDir, label + ".c"), c.getBytes(StandardCharsets.UTF_8));
                println("wrote " + label + ".c (" + c.length() + " chars)");
            } catch (Exception e) {
                println("FAILED: " + e);
            }
        }
        di.dispose();
    }
}
