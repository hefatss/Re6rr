// Disable the analyzers that exhaust the Java heap on this binary.
//
// Running analyzeHeadless twice with -Xmx12G still died in
// AddressTableAnalyzer.removeNonSearchableMemory (see docs/RECON.md). The table
// finder scans a 33 MB image with ~270k relocations; there are far too many
// candidate address sets. The demangler also floods the log with
// "Could not create Data at address ... (DemangledVariable)" because the
// binary is MSVC 2010 with no real symbols.
//
// This preScript runs after import and before analysis, so the normal analysis
// pass (functions, xrefs, decompiler inputs) still happens.
// @category Recon

import ghidra.app.script.GhidraScript;
import ghidra.framework.options.Options;

public class DisableHeavyAnalyzers extends GhidraScript {
    @Override
    public void run() throws Exception {
        Options o = currentProgram.getOptions("Analyzers");
        String[] off = {
            "Create Address Tables",
            "Data Reference.Create Address Tables",
            "Demangler Microsoft"
        };
        for (String name : off) {
            try {
                o.setBoolean(name, false);
                println("disabled: " + name);
            } catch (Exception e) {
                println("could not disable " + name + ": " + e);
            }
        }
    }
}
