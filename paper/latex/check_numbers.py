#!/usr/bin/env python3
"""Self-check: every number in paper/latex/sections/*.tex must be traceable to its "% src:" file(s).

Scope rule: a line's sources are the "% src:" paths on that line; otherwise the nearest "% src:" line in the
same paragraph/environment (scanning back, then forward, stopping at a blank line). Inside a table environment,
a "% src:" line applies to the whole environment.

A number is VERIFIED if
  (a) one of its textual variants (15.5, .155, 0.155, +2.9, 69.6 <-> 0.696, ...) occurs in a source file with
      numeric boundaries; or
  (b) a source number with one or two more decimals rounds to it (e.g. 0.133 -> 0.13, 4.09 -> 4.1); or
  (c) it is the left-hand side of a "% derived: X=expr; Y=expr" annotation on the same line whose arithmetic
      holds at X's precision and whose operands are themselves found in the line's sources (rule a/b).
Lines carrying "% nocheck" (TikZ coordinates, layout constants) are skipped.

Also checked:
  * every "% src:" path resolves to at least one existing file (MISSING_SRC otherwise);
  * REQUIRED_SOURCES (the evidence files the current draft rests on, incl. the W93 2x2 report) exist and are
    cited somewhere in sections/*.tex.

Exit code 0 only if there are no unverified numbers, no missing sources and no uncited required source.
Usage: python3 paper/latex/check_numbers.py [--report]   (--report: always exit 0)
"""
import glob
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sections")
NUM = re.compile(r"(?<![\w.\\{])(\d+(?:\.\d+)?)(?![\w])")
SRCNUM = re.compile(r"(?<![\d.])(\d+\.\d+)(?![\d])")
PATH = re.compile(r"[\w./*-]+/[\w./*-]+\.(?:md|json|jsonl|csv|py)")

# Evidence the W94 draft rests on (W93 = the 2x2 centre). Each must exist and be cited.
REQUIRED_SOURCES = [
    "analysis/fork/out/ghf_20261001T211519Z.md",            # W93: G/H/F, 3x3, 16 patterns, cases, coverage
    "analysis/fork/out/dev_all_20261001T070326Z.md",        # R1 full-pool r/d/M/G_all
    "analysis/fork/out/bank_u_f01_20261001T134456Z.md",     # R3 Bank U
    "analysis/fork/out/simctrl_20261001T212742Z.md",        # R3 simulator control (W91 relay run)
    "analysis/fork/out/token_mech_20261001T185031Z.md",     # R4 token analysis
    "analysis/fork/out/ext_20261001T135106Z.md",            # R3 BFCL / ALFWorld
    "analysis/recovery/inject_q4/summary_v2.md",            # App. injection
    "analysis/annotation/wp5/table4_v2.md",                 # App. Table 4 v2
    "docs/insights/PREREG_FORK_CONFIRM.md",                 # holdout prereg
    "analysis/insights/iter_4/out/success_ni_ALIGNED_20260930T213009Z.md",  # end-to-end comparison
]
_cache = {}


def read_src(p):
    if p not in _cache:
        txt = ""
        for f in sorted(glob.glob(os.path.join(ROOT, p))):
            try:
                txt += open(f, encoding="utf-8", errors="replace").read() + "\n"
            except IsADirectoryError:
                pass
        _cache[p] = txt.replace("\u2212", "-")
    return _cache[p]


def variants(n):
    out = {n}
    if "." in n:
        a, b = n.split(".")
        if a == "0":
            out.add("." + b)
        if a == "":
            out.add("0" + n)
        try:
            v = float(n)
            out.add(f"{v / 100:.3f}".rstrip("0"))      # percent -> fraction
            out.add(f"{v / 100:.4f}")
            out.add(f"{v / 100:.3f}")
            out.add(f"{v / 100:.3f}".lstrip("0"))
        except ValueError:
            pass
    else:
        v = int(n)
        out.add(f"{v}.0")
        out.add(f"{v / 100:.2f}")
        out.add(f"{v / 100:.3f}")
    return out


def found_exact(n, txt):
    for v in variants(n):
        if re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d])", txt):
            return True
    return False


def found_rounded(n, txt):
    """A source number with 1-2 more decimals that rounds to n (also as a percent of a fraction)."""
    dec = len(n.split(".")[1]) if "." in n else 0
    target = float(n)
    for m in SRCNUM.finditer(txt):
        s = m.group(1)
        sd = len(s.split(".")[1])
        v = float(s)
        for val, vd in ((v, sd), (v * 100, sd - 2)):
            if dec < vd <= dec + 2 and abs(round(val, dec) - target) < 1e-9 and abs(val - target) <= 0.5 * 10 ** -dec + 1e-12:
                return True
    return False


def found(n, txt):
    return found_exact(n, txt) or found_rounded(n, txt)


def split_comment(line):
    m = re.search(r"(?<!\\)%", line)
    return (line[: m.start()], line[m.start():]) if m else (line, "")


def derived_ok(com, txt):
    """Parse '% derived: X=expr; ...' and return the set of verified left-hand sides."""
    ok = set()
    m = re.search(r"derived:\s*(.*)", com)
    if not m:
        return ok
    for eq in m.group(1).split(";"):
        if "=" not in eq:
            continue
        lhs, rhs = [x.strip() for x in eq.split("=", 1)]
        rhs = rhs.split("(")[0].strip() if not re.fullmatch(r"[\d.+\-*/() ]+", rhs) else rhs
        if not re.fullmatch(r"[\d.+\-*/() ]+", rhs) or not re.fullmatch(r"\.?\d+(\.\d+)?", lhs):
            continue
        try:
            val = eval(rhs, {"__builtins__": {}}, {})
        except Exception:
            continue
        dec = len(lhs.split(".")[1]) if "." in lhs else 0
        operands = [o for o in re.findall(r"\d+(?:\.\d+)?", rhs) if o not in ("100",)]
        if abs(round(val, dec) - float(lhs)) < 1e-9 and all(found(o, txt) for o in operands):
            ok.add(lhs)
            ok.add(lhs.lstrip("0") if lhs.startswith("0.") else lhs)
            if lhs.startswith("."):
                ok.add("0" + lhs)
    return ok


def main():
    bad, missing, n_checked = [], set(), 0
    cited = set()
    for fn in sorted(glob.glob(os.path.join(SEC, "*.tex"))):
        lines = open(fn, encoding="utf-8").read().split("\n")
        srcs = []
        for ln in lines:
            body, com = split_comment(ln)
            ps = PATH.findall(com) if "src:" in com else []
            for p in ps:
                cited.add(p)
                if not glob.glob(os.path.join(ROOT, p)):
                    missing.add((os.path.basename(fn), p))
            srcs.append(ps)
        env_src, in_table = [], False
        for i, ln in enumerate(lines):
            body, com = split_comment(ln)
            if re.search(r"\\begin\{table", body):
                in_table, env_src = True, []
            if in_table and srcs[i]:
                env_src = env_src + srcs[i]
            if re.search(r"\\end\{table", body):
                in_table = False
            if "nocheck" in com:
                continue
            # strip things that are not claims
            b = re.sub(r"\\(ref|label|cite[pt]?|citep|citet|nolinkurl|url|input|begin|end)\{[^}]*\}", "", body)
            b = re.sub(r"\\setlength\{[^}]*\}\{[^}]*\}|\\resizebox\{[^}]*\}\{[^}]*\}", "", b)
            b = re.sub(r"\\(multirow|multicolumn)\{\d+\}", "", b)
            b = re.sub(r"tabcolsep|\d+(\.\d+)?(pt|cm)", "", b)
            nums = NUM.findall(b)
            if not nums:
                continue
            here = srcs[i] or (env_src if in_table else [])
            if not here:
                for j in range(i - 1, -1, -1):
                    if not lines[j].strip():
                        break
                    if srcs[j]:
                        here = srcs[j]
                        break
            if not here:
                for j in range(i + 1, len(lines)):
                    if not lines[j].strip():
                        break
                    if srcs[j]:
                        here = srcs[j]
                        break
            txt = "".join(read_src(p) for p in here)
            dok = derived_ok(com, txt) if "derived:" in com else set()
            for n in nums:
                n_checked += 1
                if n in dok or ("." in n and n.startswith("0") and n[1:] in dok):
                    continue
                if not here or not found(n, txt):
                    bad.append((os.path.basename(fn), i + 1, n, here))
    uncited = [p for p in REQUIRED_SOURCES if p not in cited or not os.path.exists(os.path.join(ROOT, p))]
    print(f"checked {n_checked} number occurrences; unverified {len(bad)}; missing src paths {len(missing)}; "
          f"uncited/missing required sources {len(uncited)}")
    for f, l, n, h in bad:
        print(f"UNVERIFIED {f}:{l}: {n}   src={h or 'NONE'}")
    for f, p in sorted(missing):
        print(f"MISSING_SRC {f}: {p}")
    for p in uncited:
        print(f"REQUIRED_SOURCE_NOT_CITED {p}")
    ok = not bad and not missing and not uncited
    print("PASS" if ok else "FAIL")
    return 0 if (ok or "--report" in sys.argv) else 1


if __name__ == "__main__":
    sys.exit(main())
