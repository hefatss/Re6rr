// Print the analysis options and analyzer names of the imported program, then
// exit. Used to find the option that turns off the address-table analyzer that
// exhausts the heap on this 33 MB binary.
// @category Recon

import ghidra.app.script.GhidraScript;
import ghidra.framework.options.Options;

public class PrintOptions extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (String cat : currentProgram.getOptionsNames()) {
            println("CAT " + cat);
            Options o = currentProgram.getOptions(cat);
            for (String n : o.getOptionNames()) {
                println("  OPT " + n + " = " + o.getObject(n, null));
            }
        }
    }
}
