"""E4-2 tasks: fork-alternative open loop (scripts/a6000/openloop_topk.py) for BF16 and each checkpoint cell.

Task id a6k2_<m>_olk_<cell>, priority -8, no closed-loop runs. The openloop dict has topk 20, positions first,tool,
first_all, n 400 and seed 0 (the same decision sample as E3). Output goes to analysis/openloop/a6k2/<m>/topk/<cell>.
Every non-BF16 cell depends on a6k2_<m>_olk_bf16 and passes it as --ref, so its summary already contains the
served-vs-served contrasts (KL, Δlogit P(act), Δ tool-name mass). Checkpoint specs and calibration deps are copied
from the matching closed-loop task a6k2_<m>_<cell>. Fixed Gaussian k=1 seeds use {"kind":"gauss","k":1.0,"seed":s}.
Existing task ids are never overwritten. Plan: docs/insights/iter_4_disposition.md (E4-2); RESEARCH_LOG W20.

usage: python scripts/a6000/make_tasks_e42.py [--dry] [--smoke]   (--smoke: q4 bf16 + rtn_w4 only)
"""
import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
DIRS = ("todo", "running", "done", "failed", "deferred")
BASE = ["rtn_w4", "gptq_w4_d1", "gptq_w4_d2", "awq_w4", "rtn_w3"]
CELLS = {
    "q4": BASE + ["awq_w4_d2", "gshape_w4", "rtnsign_w4", "nf4", "mxfp4", "rot_rtn_w4", "rot_gptq_w4",
                  "gptq_w4_d3", "gptq_w4_d4", "awq_w4_d3", "awq_w4_d4"] + [f"gauss1_s{s}" for s in (1, 2, 4, 5)],
    "q8": BASE + ["awq_w4_d2", "gshape_w4", "rtnsign_w4",
                  "gptq_w4_d3", "gptq_w4_d4", "awq_w4_d3", "awq_w4_d4"] + [f"gauss1_s{s}" for s in (1, 2, 4, 5)],
    "q14": BASE,
    "q32": BASE,
}


def where(tid):
    for d in DIRS:
        if (Q / d / f"{tid}.json").exists():
            return d
    return None


def load(tid):
    d = where(tid)
    return json.load(open(Q / d / f"{tid}.json")) if d else None


def spec(m, cell):
    if cell == "bf16":
        return {"kind": "bf16"}, "bf16", []
    if cell.startswith("gauss1_s"):
        return {"kind": "gauss", "k": 1.0, "seed": int(cell[8:])}, "gauss", []
    src = load(f"a6k2_{m}_{cell}")
    if src is None:
        return None
    return src["ckpt"], src["arm"], [x for x in src.get("deps", []) if "calib" in x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    plan = {"q4": ["rtn_w4"]} if a.smoke else CELLS
    new, missing = [], []
    for m, cells in plan.items():
        ref = f"analysis/openloop/a6k2/{m}/topk/bf16"
        for cell in ["bf16"] + cells:
            tid = f"a6k2_{m}_olk_{cell}"
            if where(tid) is not None:
                continue
            s = spec(m, cell)
            if s is None:
                missing.append(tid)
                continue
            ck, arm, deps = s
            ol = {"ref_runs": [f"a6k2_{m}_bf16"], "n": 400, "topk": 20, "positions": "first,tool", "first_all": True,
                  "out": f"analysis/openloop/a6k2/{m}/topk/{cell}"}
            deps = deps + [f"a6k2_{m}_bf16"]
            if cell != "bf16":
                ol["ref"] = ref
                deps.append(f"a6k2_{m}_olk_bf16")
            new.append({"id": tid, "kind": "eval", "model": m, "arm": arm, "ckpt": ck, "runs": [], "priority": -8,
                        "deps": deps, "openloop": ol})
    for t in new:
        print("NEW ", t["id"], t["ckpt"], t["deps"])
    for tid in missing:
        print("MISS", tid, "(no closed-loop task to copy the checkpoint spec from)")
    print(len(new), "new tasks")
    if not a.dry:
        for t in new:
            json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
