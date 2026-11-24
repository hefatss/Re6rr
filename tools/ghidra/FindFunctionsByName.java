// List functions and labels whose name contains a substring.
//
//   analyzeHeadless <proj> wmn6r -process wmn6r.exe -noanalysis \
//       -scriptPath tools/ghidra -postScript FindFunctionsByName.java SetDefault
// @category Recon

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;

public class FindFunctionsByName extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("usage: FindFunctionsByName.java <substring>");
            return;
        }
        String needle = args[0];
        FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
        while (functions.hasNext()) {
            Function function = functions.next();
            if (function.getName().contains(needle)) {
                println("FUNC " + function.getName() + " @ " +
                        function.getEntryPoint() + " size " +
                        function.getBody().getNumAddresses());
            }
        }
        SymbolIterator symbols = currentProgram.getSymbolTable().getAllSymbols(true);
        while (symbols.hasNext()) {
            Symbol symbol = symbols.next();
            if (symbol.getName().contains(needle)) {
                println("SYM " + symbol.getName() + " @ " + symbol.getAddress() +
                        " type " + symbol.getSymbolType());
            }
        }
    }
}
