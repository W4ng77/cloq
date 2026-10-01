#!/usr/bin/env python3
"""Self-check: every number in paper/latex/sections/*.tex must appear in its "% src:" file(s).

Scope rule: a line's sources are the "% src:" paths on that line; otherwise the nearest "% src:" line in the
same paragraph/environment (scanning back, then forward, stopping at a blank line). Inside a table environment,
a "% src:" line applies to the whole environment. A number is VERIFIED if one of its textual variants
(e.g. 15.5, .155, 0.155, +2.9, 0.118 <-> .118, 69.6 <-> 0.696) occurs in one of its source files with numeric
boundaries. Output: a list of UNVERIFIED numbers (file:line, number, sources) for manual review.
Usage: python3 paper/latex/check_numbers.py  (run from the repo root or anywhere; paths resolve to the repo root)
"""
import glob
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sections")
NUM = re.compile(r"(?<![\w.\\{])(\d+(?:\.\d+)?)(?![\w])")
PATH = re.compile(r"[\w./*-]+/[\w./*-]+\.(?:md|json|jsonl|csv|py)")
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


def found(n, txt):
    for v in variants(n):
        if re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d])", txt):
            return True
    return False


def split_comment(line):
    m = re.search(r"(?<!\\)%", line)
    return (line[: m.start()], line[m.start():]) if m else (line, "")


def main():
    bad, n_checked = [], 0
    for fn in sorted(glob.glob(os.path.join(SEC, "*.tex"))):
        lines = open(fn, encoding="utf-8").read().split("\n")
        srcs = []
        for ln in lines:
            body, com = split_comment(ln)
            srcs.append(PATH.findall(com) if "src:" in com else [])
        env_src, in_table = [], False
        for i, ln in enumerate(lines):
            body, com = split_comment(ln)
            if re.search(r"\\begin\{table", body):
                in_table, env_src = True, []
            if in_table and srcs[i]:
                env_src = env_src + srcs[i]
            if re.search(r"\\end\{table", body):
                in_table = False
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
            for n in nums:
                n_checked += 1
                if not here or not found(n, txt):
                    bad.append((os.path.basename(fn), i + 1, n, here))
    print(f"checked {n_checked} number occurrences; unverified {len(bad)}")
    for f, l, n, h in bad:
        print(f"UNVERIFIED {f}:{l}: {n}   src={h or 'NONE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
