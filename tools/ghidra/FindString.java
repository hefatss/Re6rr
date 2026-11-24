// Locate string literals by substring and list the code that references them.
//
//   analyzeHeadless <proj> wmn6r -process wmn6r.exe -noanalysis \
//       -scriptPath <this dir> -postScript FindString.java <out dir> <substring>...
// @category Recon

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.DataUtilities;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.util.task.ConsoleTaskMonitor;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.LinkedHashSet;
import java.util.Set;

public class FindString extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("usage: FindString.java <out dir> <substring>...");
            return;
        }
        String outDir = args[0];
        Files.createDirectories(Paths.get(outDir));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        ConsoleTaskMonitor monitor = new ConsoleTaskMonitor();
        Set<Function> funcs = new LinkedHashSet<>();

        for (int a = 1; a < args.length; a++) {
            String needle = args[a];
            println("=== substring " + needle);
            DataIterator it = currentProgram.getListing().getDefinedData(true);
            int hits = 0;
            while (it.hasNext() && hits < 40) {
                Data d = it.next();
                StringDataInstance s = StringDataInstance.getStringDataInstance(d);
                if (s == null) continue;
                String value = s.getStringValue();
                if (value == null || !value.contains(needle)) continue;
                hits++;
                Address at = d.getAddress();
                println("  string @" + at + " = " + value);
                Reference[] refs = getReferencesTo(at);
                println("  refs " + refs.length);
                for (Reference r : refs) {
                    Function f = currentProgram.getFunctionManager()
                                        .getFunctionContaining(r.getFromAddress());
                    println("    " + r.getFromAddress() + " " + r.getReferenceType() +
                            " in " + (f == null ? "?" : f.getName() + " @" + f.getEntryPoint()));
                    if (f != null) funcs.add(f);
                }
            }
            println("  hits " + hits);
        }

        for (Function f : funcs) {
            String label = "str_" + f.getEntryPoint().toString().replace(":", "_");
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
