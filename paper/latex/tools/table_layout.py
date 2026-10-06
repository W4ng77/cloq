"""Readable appendix tables without whole-table scaling.

Presentation only: wide column sets become stacked panels. Every data cell is
copied literally; point estimates and intervals are never parsed or recomputed.
Used by gen_w93_tables.py for the generated tables, and by the one-time layout
pass for the authored appendix tables.
"""
import re


def split_cells(row):
    """Split unescaped ampersands outside braces (safe for math and macros)."""
    cells, start, depth = [], 0, 0
    for i, ch in enumerate(row):
        escaped = i > 0 and row[i - 1] == "\\"
        if ch == "{" and not escaped:
            depth += 1
        elif ch == "}" and not escaped:
            depth -= 1
        elif ch == "&" and not escaped and depth == 0:
            cells.append(row[start:i].strip()); start = i + 1
    return cells + [row[start:].strip()]


def restyle_table(block, panels=None):
    if "% visual-layout-v1" in block:
        return block
    block = block.replace("\\scriptsize", "\\fontsize{8.5}{10}\\selectfont")
    block = re.sub(r"\\setlength\{\\tabcolsep\}\{[^}]+\}",
                   r"\\setlength{\\tabcolsep}{4pt}", block)
    block = re.sub(r"\\resizebox\{[^}]+\}\{!\}\{(?:%\s*)?(?=\\begin\{tabular\})", "", block)
    block = block.replace("\\end{tabular}}", "\\end{tabular}")
    # Full-width floats allow an eight-point print font, instead of shrinking it.
    block = re.sub(r"\\begin\{table\}\[[^]]*\]", r"\\begin{table*}[t]", block)
    block = block.replace("\\end{table}", "\\end{table*}")
    block = block.replace("\\centering", "\\centering% visual-layout-v1\n\\renewcommand{\\arraystretch}{1.12}", 1)
    if panels is None:
        return block
    mat = re.search(r"\\begin\{tabular\}\{.*\}\n(.*?)\\end\{tabular\}", block, re.S)
    if not mat:
        raise ValueError("Cannot find tabular body")
    lines = mat.group(1).splitlines()
    parsed = []
    for line in lines:
        # Panel headers replace the old multicolumn grouping headers.
        if "\\multicolumn" in line or "\\cmidrule" in line:
            continue
        if "&" not in line:
            if line.strip() not in ("\\toprule", "\\bottomrule"):
                parsed.append(line)
            continue
        content, sep, comment = line.partition(" %")
        content = re.sub(r"\\\\\s*$", "", content)
        parsed.append((split_cells(content), " %" + comment if sep else ""))
    pieces = []
    for title, cols in panels:
        n = len(cols)
        pieces += ["\\begin{tabular*}{\\textwidth}{@{\\extracolsep{\\fill}}l" + "l" * (n-1) + "@{}}",
                   "\\toprule", "\\multicolumn{"+str(n)+"}{@{}l}{\\textbf{"+title+"}} \\\\", "\\addlinespace[2pt]"]
        for item in parsed:
            if isinstance(item, str):
                pieces.append(item)
            else:
                cells, comment = item
                if max(cols) >= len(cells):
                    raise ValueError((title, len(cells), cells))
                pieces.append(" & ".join(cells[c] for c in cols) + " \\\\" + comment)
        pieces += ["\\bottomrule", "\\end{tabular*}", "\\par\\vspace{6pt}"]
    return block[:mat.start()] + "\n".join(pieces) + block[mat.end():]


PANELS = {
    "tab:ghf": [("A. Gains and action--continuation comparison", [0,1,2,3,4,5]),
                ("B. Joint-upgrade contrasts and outcome patterns", [0,6,7,8,9,10])],
    "tab:classes": [("A. Sensitivity to the action and continuation", [0,1,2,3,4]),
                    ("B. Outcome classes and named patterns", [0,5,6,7,8,9,10,11])],
    "tab:patternref": [("A. Joint rescue", [0,1,2,3,4,5]),
                       ("B. Rescue undone", [0,1,6,7,8,9])],
    "tab:oracle": [("A. Frozen trigger and matched hindsight oracle", [0,1,2,3,4]),
                   ("B. Post hoc KL reference (requires BF16)", [0,5,6,7,8])],
    "tab:extr2": [("A. Full item pool", [0,1,2,3,4,5]),
                  ("B. First divergent states", [0,6,7,8,9,10,11])],
    "tab:patterns": [("A. Qwen3-4B configurations", list(range(6))),
                     ("B. Qwen3-8B configurations", [0]+list(range(6,12)))],
    "tab:ghf-crossed": [("A. Upgrade gains", [0,1,2,3]),
                        ("B. Paired differences between upgrade modes", [0,4,5,6])],
}


def format_tables(source):
    def one(match):
        block = match.group(0)
        label = re.search(r"\\label\{([^}]+)\}", block)
        return restyle_table(block, PANELS.get(label.group(1)) if label else None)
    return re.sub(r"\\begin\{table\*?\}\[[^]]*\].*?\\end\{table\*?\}", one, source, flags=re.S)
