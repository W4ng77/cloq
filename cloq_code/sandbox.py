"""Deterministic Python subprocess sandbox (no containers).

One fresh `python -I` process per test case, in a private temp dir, with a minimal environment
(PYTHONHASHSEED=0, random seeded to 0) and rlimits: CPU seconds (the time limit; CPU time instead of wall time so
that verdicts do not depend on node load), address space, output file size, core dumps off. A wall-clock guard
(much larger than the CPU limit) catches sleeping/blocked programs; it is reported separately (`wall_timeout`)
because it is the one verdict that could depend on load.

Two LiveCodeBench test types:
  stdin       the program reads the input on stdin; stdout is compared token-wise (floats with 1e-6 tolerance)
  functional  LeetCode style: `class Solution` with method `func_name`; each input line is one JSON argument; the
              JSON result is compared after tuple->list normalisation (floats with 1e-6 tolerance)
Everything that reaches the model (feedback) is made deterministic: fixed file name, no temp paths, hex addresses
masked, fixed truncation lengths.
"""

from __future__ import annotations

import json
import math
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

CPU_LIMIT_S = int(os.environ.get("CLOQ_CODE_CPU_LIMIT", "6"))  # LCB's per-test timeout is 6 s
WALL_LIMIT_S = int(os.environ.get("CLOQ_CODE_WALL_LIMIT", "60"))
MEM_LIMIT_B = int(os.environ.get("CLOQ_CODE_MEM_MB", "6144")) * 2**20
FSIZE_LIMIT_B = 512 * 2**20
PYTHON = os.environ.get("CLOQ_CODE_PYTHON", sys.executable)
# Concurrent sandbox processes (CPU-time limits keep verdicts load-independent; this only bounds node load).
_SEM = threading.BoundedSemaphore(int(os.environ.get("CLOQ_CODE_SANDBOX_PAR", "4")))

PRELUDE = (
    "from string import *\nfrom re import *\nfrom datetime import *\nfrom collections import *\nfrom heapq import *\n"
    "from bisect import *\nfrom copy import *\nfrom math import *\nfrom random import *\nfrom statistics import *\n"
    "from itertools import *\nfrom functools import *\nfrom operator import *\nfrom io import *\nfrom sys import *\n"
    "from json import *\nfrom builtins import *\nfrom typing import *\n"
    "import string, re, datetime, collections, heapq, bisect, copy, math, random, statistics, itertools, functools, "
    "operator, io, sys, json\nsys.setrecursionlimit(50000)\n"
)

STDIN_RUNNER = (
    "import random, runpy, sys\nrandom.seed(0)\nsys.argv = ['solution.py']\n"
    "runpy.run_path('solution.py', run_name='__main__')\n"
)

FUNC_RUNNER = (
    "import json, random, sys\nrandom.seed(0)\n"
    "src = open('solution.py').read()\n"
    "ns = {'__name__': 'solution'}\n"
    "exec(compile(open('prelude.py').read(), 'prelude.py', 'exec'), ns)\n"
    "exec(compile(src, 'solution.py', 'exec'), ns)\n"
    "args = [json.loads(l) for l in open('input.txt').read().split('\\n') if l.strip()]\n"
    "fn = getattr(ns['Solution'](), sys.argv[1])\n"
    "res = fn(*args)\n"
    "def norm(x):\n"
    "    if isinstance(x, tuple): x = list(x)\n"
    "    if isinstance(x, list): return [norm(y) for y in x]\n"
    "    if isinstance(x, dict): return {str(k): norm(v) for k, v in x.items()}\n"
    "    return x\n"
    "open('result.json', 'w').write(json.dumps(norm(res)))\n"
)

HEX = re.compile(r"0x[0-9a-fA-F]{6,}")


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_S, CPU_LIMIT_S + 1))
    resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT_B, MEM_LIMIT_B))
    resource.setrlimit(resource.RLIMIT_FSIZE, (FSIZE_LIMIT_B, FSIZE_LIMIT_B))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.setsid()


@dataclass
class TestResult:
    verdict: str  # AC | WA | RE | TLE | MLE | OLE | wall_timeout | sandbox_error
    stderr: str = ""
    got: str = ""
    detail: dict = field(default_factory=dict)


def extract_code(text: str | None) -> str | None:
    """Last complete ```python (or bare ```) block; None if there is none. A block left unclosed because the reply
    hit max_tokens is "no code" (never executed), and the model is told so in the feedback."""
    if not text:
        return None
    blocks = re.findall(r"```[ \t]*(?:python3?|py)?[ \t]*\n(.*?)```", text, flags=re.S | re.I)
    return blocks[-1] if blocks else None


def count_code_blocks(text: str | None) -> int:
    return len(re.findall(r"```[ \t]*(?:python3?|py)?[ \t]*\n(.*?)```", text or "", flags=re.S | re.I))


def _clean(s: str, n: int) -> str:
    s = HEX.sub("0x…", s.rstrip())
    return s if len(s) <= n else s[: n // 2] + "\n…[truncated]…\n" + s[-n // 2:]


def _tail(s: str, n: int) -> str:
    s = HEX.sub("0x…", s)
    return s if len(s) <= n else "…[truncated]…\n" + s[-n:]


def _sanitize_tb(err: str, d: str) -> str:
    """Drop the harness frames (runner.py / runpy) and the temp-dir path so feedback is node- and run-invariant."""
    err = err.replace(d + os.sep, "").replace(d, ".")
    lines = err.splitlines()
    try:
        i = next(k for k, ln in enumerate(lines) if ln.lstrip().startswith('File "solution.py"'))
        j = max(k for k, ln in enumerate(lines[:i]) if ln.startswith("Traceback (most recent call last)"))
        lines = lines[: j + 1] + lines[i:]
    except (StopIteration, ValueError):
        pass
    return "\n".join(lines)


def _floats_equal(a: str, b: str) -> bool:
    try:
        x, y = float(a), float(b)
    except ValueError:
        return False
    if math.isnan(x) or math.isnan(y):
        return False
    return math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-6)


def compare_stdout(got: str, expected: str) -> bool:
    g = [ln.split() for ln in got.strip().splitlines()]
    e = [ln.split() for ln in expected.strip().splitlines()]
    g = [x for x in g if x]
    e = [x for x in e if x]
    if g == e:
        return True
    if len(g) != len(e) or any(len(a) != len(b) for a, b in zip(g, e)):
        return False
    return all(ta == tb or _floats_equal(ta, tb) for a, b in zip(g, e) for ta, tb in zip(a, b))


def _eq_json(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b or (math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq_json(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_eq_json(a[k], b[k]) for k in a)
    return a == b


def run_one(code: str, test: dict, testtype: str, func_name: str | None) -> TestResult:
    """Run one test case in a fresh process. Never raises for program faults; sandbox faults -> sandbox_error."""
    with _SEM:
        d = tempfile.mkdtemp(prefix="cloqcode_", dir=os.environ.get("CLOQ_CODE_TMP") or None)
        try:
            p = Path(d)
            (p / "input.txt").write_text(test["input"])
            if testtype == "functional":
                (p / "solution.py").write_text(code)
                (p / "prelude.py").write_text(PRELUDE)
                (p / "runner.py").write_text(FUNC_RUNNER)
                argv = [PYTHON, "-I", "runner.py", func_name or ""]
            else:
                (p / "solution.py").write_text(code)
                (p / "runner.py").write_text(STDIN_RUNNER)
                argv = [PYTHON, "-I", "runner.py"]
            env = {"PYTHONHASHSEED": "0", "PATH": "/usr/bin:/bin", "HOME": d, "LANG": "C.UTF-8",
                   "PYTHONIOENCODING": "utf-8", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
            with open(p / "input.txt", "rb") as fin, open(p / "stdout.txt", "wb") as fout, open(p / "stderr.txt", "wb") as ferr:
                proc = subprocess.Popen(argv, cwd=d, stdin=fin, stdout=fout, stderr=ferr, env=env, preexec_fn=_limits)
                wall = False
                try:
                    proc.wait(timeout=WALL_LIMIT_S)
                except subprocess.TimeoutExpired:
                    wall = True
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()
            rc = proc.returncode
            err = _sanitize_tb((p / "stderr.txt").read_bytes()[-20000:].decode("utf-8", "replace"), d)
            out = (p / "stdout.txt").read_bytes().decode("utf-8", "replace")
            if wall:
                return TestResult("wall_timeout", err, out[:4000])
            if rc in (-signal.SIGXCPU, -signal.SIGKILL) and ("MemoryError" not in err):
                return TestResult("TLE", err, out[:4000])
            if rc == -signal.SIGXFSZ:
                return TestResult("OLE", err, "")
            if rc != 0:
                return TestResult("MLE" if "MemoryError" in err else "RE", err, out[:4000])
            if testtype == "functional":
                try:
                    res = json.loads((p / "result.json").read_text())
                except Exception as e:  # program exited 0 without a result (e.g. sys.exit in the method)
                    return TestResult("RE", err + f"\n(no return value recorded: {type(e).__name__})", out[:4000])
                exp = json.loads(test["output"])
                got_s = json.dumps(res)
                return TestResult("AC" if _eq_json(res, exp) else "WA", err, got_s[:4000])
            return TestResult("AC" if compare_stdout(out, test["output"]) else "WA", err, out[:4000])
        except Exception as e:  # our fault, not the program's
            return TestResult("sandbox_error", repr(e))
        finally:
            shutil.rmtree(d, ignore_errors=True)


def run_tests(code: str, tests: list[dict], testtype: str, func_name: str | None, stop_at_first_fail: bool) -> dict:
    results = []
    for i, t in enumerate(tests):
        r = run_one(code, t, testtype, func_name)
        results.append(r)
        if r.verdict == "sandbox_error":
            break
        if stop_at_first_fail and r.verdict != "AC":
            break
    verdicts = [r.verdict for r in results]
    n_pass = sum(v == "AC" for v in verdicts)
    first_fail = next((i for i, v in enumerate(verdicts) if v != "AC"), None)
    return {
        "passed": n_pass == len(tests) and len(results) == len(tests),
        "n_pass": n_pass, "n_tests": len(tests), "n_run": len(results), "verdicts": verdicts,
        "first_fail": first_fail, "sandbox_error": "sandbox_error" in verdicts,
        "wall_timeout": "wall_timeout" in verdicts, "_results": results,
    }


VERDICT_TEXT = {"WA": "Wrong Answer", "RE": "Runtime Error", "TLE": f"Time Limit Exceeded (CPU limit {CPU_LIMIT_S} s)",
                "MLE": "Memory Limit Exceeded", "OLE": "Output Limit Exceeded",
                "wall_timeout": f"Time Limit Exceeded (wall-clock limit {WALL_LIMIT_S} s)"}


def feedback_text(res: dict, tests: list[dict], testtype: str) -> str:
    """Deterministic execution feedback shown to the model after a failing public run."""
    i = res["first_fail"]
    r: TestResult = res["_results"][i]
    t = tests[i]
    lines = [f"Your program was run on the {res['n_tests']} public example test(s): {res['n_pass']} passed, "
             f"{res['n_tests'] - res['n_pass']} failed.",
             f"First failing test: #{i + 1} — {VERDICT_TEXT.get(r.verdict, r.verdict)}.", "", "Input:",
             _clean(t["input"], 800), "", "Expected output:", _clean(t["output"], 800)]
    if r.verdict == "WA":
        lines += ["", "Your output:", _clean(r.got, 800) if r.got.strip() else "(empty)"]
    if r.verdict in ("RE", "MLE") or (r.verdict == "WA" and r.stderr.strip()):
        lines += ["", "Error output (stderr):", _tail(r.stderr.strip(), 1500)]
    lines += ["", "Fix the program and reply with the complete corrected program in a single ```python code block."]
    return "\n".join(lines)
