// Find code references to literal data addresses in the analysed program and
// export the containing functions as C.
//
//   analyzeHeadless <proj> wmn6r -process wmn6r.exe -noanalysis \
//       -scriptPath <this dir> -postScript FindXrefs.java <out dir> 0xADDR...
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
import java.util.LinkedHashSet;
import java.util.Set;

public class FindXrefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("usage: FindXrefs.java <out dir> <addr>...");
            return;
        }
        String outDir = args[0];
        Files.createDirectories(Paths.get(outDir));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        ConsoleTaskMonitor monitor = new ConsoleTaskMonitor();
        Set<Function> funcs = new LinkedHashSet<>();

        for (int i = 1; i < args.length; i++) {
            Address at = currentProgram.getAddressFactory().getAddress(args[i]);
            if (at == null) {
                println("bad address " + args[i]);
                continue;
            }
            println("=== target " + at);
            Reference[] refs = getReferencesTo(at);
            println("refs " + refs.length);
            for (Reference r : refs) {
                Address from = r.getFromAddress();
                println("  " + from + " " + r.getReferenceType());
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                if (f != null) {
                    println("    in " + f.getName() + " @" + f.getEntryPoint());
                    funcs.add(f);
                }
            }
        }

        for (Function f : funcs) {
            String label = "xref_" + f.getEntryPoint().toString().replace(":", "_");
            try {
                DecompileResults res = di.decompileFunction(f, 120, monitor);
                if (!res.decompileCompleted()) {
                    println("FAILED " + label + ": " + res.getErrorMessage());
                    continue;
                }
                String c = res.getDecompiledFunction().getC();
                Files.write(Paths.get(outDir, label + ".c"), c.getBytes(StandardCharsets.UTF_8));
                println("wrote " + label + ".c (" + c.length() + " chars)");
            } catch (Exception e) {
                println("FAILED " + label + ": " + e);
            }
        }
        di.dispose();
    }
}
