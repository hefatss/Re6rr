// Decompile a list of functions from the already-analysed Ghidra project.
//
//   analyzeHeadless <proj> wmn6r -process wmn6r.exe -noanalysis \
//       -scriptPath <this dir> -postScript ExportDecomp.java <out dir> <list file>
//
// List file: one "0xSTART 0xEND name" per line. Output: <out dir>/<name>.c.
//
// Ghidra's auto-analysis creates ~139k functions, but not always at .pdata
// starts; where exact lookup fails we use the enclosing function or create one
// from the .pdata bounds. Newly created functions sometimes decompile to
// halt_baddata() because Ghidra will not disassemble at those entries; those
// are reported as failures rather than silently written as valid C.
// @category Recon

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.SourceType;
import ghidra.util.task.ConsoleTaskMonitor;

import java.io.BufferedReader;
import java.io.FileReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

public class ExportDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] scriptArgs = getScriptArgs();
        if (scriptArgs.length < 2) {
            println("usage: ExportDecomp.java <out dir> <list file>");
            return;
        }
        String outDir = scriptArgs[0];
        String listFile = scriptArgs[1];
        Files.createDirectories(Paths.get(outDir));

        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        ConsoleTaskMonitor monitor = new ConsoleTaskMonitor();
        int done = 0, failed = 0;

        try (BufferedReader br = new BufferedReader(new FileReader(listFile))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.length() == 0 || line.startsWith("#")) continue;
                String[] parts = line.split("\\s+");
                Address at = currentProgram.getAddressFactory().getAddress(parts[0]);
                String label = parts.length > 2 ? parts[2] : "f_" + parts[0].replace("0x", "");
                Function f = currentProgram.getFunctionManager().getFunctionAt(at);
                if (f != null && f.getName().startsWith("f_")) {
                    // A previous run created this function before its body was
                    // disassembled; rebuild it from .pdata bounds.
                    currentProgram.getFunctionManager().removeFunction(at);
                    f = null;
                }
                if (f == null) {
                    // .pdata entries are often chunks of a larger function;
                    // Ghidra merges them, so use the enclosing function.
                    f = currentProgram.getFunctionManager().getFunctionContaining(at);
                    if (f != null) {
                        println("using enclosing " + f.getEntryPoint() + " for " + parts[0]);
                    }
                }
                if (f == null) {
                    // Some .pdata entries were never turned into functions by
                    // auto-analysis. Create one at the entry for decompilation.
                    try {
                        Address end = currentProgram.getAddressFactory().getAddress(parts[1]);
                        Address cur = at;
                        while (cur != null && cur.compareTo(end) < 0) {
                            if (!disassemble(cur)) break;  // one instruction
                            Instruction ins = getInstructionAt(cur);
                            if (ins == null || ins.getLength() <= 0) break;
                            cur = ins.getAddress().add(ins.getLength());
                        }
                        f = currentProgram.getFunctionManager().createFunction(
                                label, null, at, new AddressSet(at, end), SourceType.ANALYSIS);
                        println("created function at " + parts[0] + "-" + parts[1]);
                        // The decompiler caches the program at openProgram();
                        // reopen after changing the function manager.
                        di.dispose();
                        di = new DecompInterface();
                        di.openProgram(currentProgram);
                    } catch (Exception e) {
                        println("NO FUNCTION " + parts[0] + ": " + e.getMessage());
                        failed++;
                        continue;
                    }
                }
                DecompileResults res;
                try {
                    res = di.decompileFunction(f, 90, monitor);
                } catch (Exception e) {
                    println("FAILED " + label + ": " + e);
                    failed++;
                    continue;
                }
                if (!res.decompileCompleted()) {
                    println("FAILED " + label + ": " + res.getErrorMessage());
                    failed++;
                    continue;
                }
                String c = res.getDecompiledFunction().getC();
                if (c.contains("halt_baddata")) {
                    println("FAILED " + label + ": Ghidra could not disassemble at " + parts[0]);
                    failed++;
                    continue;
                }
                Files.write(Paths.get(outDir, label + ".c"), c.getBytes(StandardCharsets.UTF_8));
                done++;
            }
        }
        println("decompiled " + done + ", failed " + failed);
        di.dispose();
    }
}
