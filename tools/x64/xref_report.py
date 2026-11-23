"""Turn the string-xref table into "which function owns which engine name".

    python tools/x64/xref_report.py [--in docs/recon/xrefs.json] [--out docs/recon/XREFS.md]

Ranking by number of referenced binding names finds the registration/dispatch
code: the function that hands the Lua-visible names to the engine (or the table
initialiser that fills it) stands out immediately.
"""

import argparse
import collections
import json
import os
import sys


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=os.path.join(root, "docs", "recon", "xrefs.json"))
    ap.add_argument("--out", default=os.path.join(root, "docs", "recon", "XREFS.md"))
    args = ap.parse_args()

    data = json.load(open(args.src, encoding="utf8"))
    hits = data["hits"]
    by_func = collections.defaultdict(set)
    for name, funcs in hits.items():
        for f in funcs:
            by_func[f].add(name)

    ranked = sorted(by_func.items(), key=lambda kv: -len(kv[1]))
    lines = ["# Engine names → implementing functions", "",
             "From `tools/x64/string_xref.py`: %d of %d Lua-called names were found as strings that some "
             "function loads with a RIP-relative operand." % (len(hits), data["names_requested"] or len(hits)), "",
             "## Functions by number of names they touch", "",
             "| function | names | examples |", "|---|---|---|"]
    for f, names in ranked[:25]:
        ex = ", ".join(sorted(names)[:6])
        lines.append("| `f_%x` | %d | %s |" % (f, len(names), ex))

    lines += ["", "## Names with more than one implementing function", ""]
    multi = {k: v for k, v in hits.items() if len(v) > 1}
    for k in sorted(multi):
        lines.append("- `%s` → %s" % (k, ", ".join("`f_%x`" % a for a in multi[k])))

    lines += ["", "## Full list", "", "| name | function |", "|---|---|"]
    for k in sorted(hits):
        lines.append("| `%s` | %s |" % (k, ", ".join("`f_%x`" % a for a in hits[k])))
    lines.append("")

    with open(args.out, "w", encoding="utf8") as fh:
        fh.write("\n".join(lines))
    print("functions hit :", len(by_func))
    print("top           :", ", ".join("f_%x(%d)" % (f, len(n)) for f, n in ranked[:8]))
    print("wrote         :", args.out)


if __name__ == "__main__":
    sys.exit(main())
