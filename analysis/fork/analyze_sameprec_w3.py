"""W3 same-precision analysis (docs/insights/SAMEPREC_W3_PROTOCOL_20261002.md; manifests/fork/sameprec_w3_v1.json).

Thin wrapper over analysis/fork/analyze_sameprec.py (SAMEPREC + Amendment A1 code, imported unchanged): the manifest, the
cell (gptq_w3), the protocol guard (sha256 of the W3 protocol must equal the manifest value) and the output name
(analysis/fork/out/sameprec_w3_<UTC>.{md,json}) are replaced; estimators, admission, TOST and readings are the same code.
The precision side is the W3 stress dev fork (analysis/fork/stress/<m>_gptq_w3, blocks q3-q5).

usage: python analysis/fork/analyze_sameprec_w3.py [--B 2000]
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_sameprec as S  # noqa: E402

ROOT = S.ROOT
MAN = ROOT / "manifests/fork/sameprec_w3_v1.json"
SNAPSHOT = "analysis/insights/iter_3/out/snapshot_auto_20261001T0600Z.json"  # the SAMEPREC snapshot (admits q3-q5 W3 blocks)


def guard(man: dict) -> str:
    s = S.AD.sha256(ROOT / man["protocol"])
    if s != man["protocol_sha256"]:
        raise SystemExit(f"analyze_sameprec_w3: refusing: sha256({man['protocol']}) = {s} != pre-registered {man['protocol_sha256']}")
    return s


def main():
    import json
    man = json.load(open(MAN))
    man.setdefault("snapshot", SNAPSHOT)
    tmpman = Path(tempfile.mkdtemp(dir=str(ROOT / "analysis/fork/out"))) / "man.json"
    tmpman.write_text(json.dumps(man))
    outdir = tmpman.parent
    S.MANIFEST, S.CELL, S.guard, S.OUT = tmpman, man["cell"], guard, outdir
    try:
        S.main()
        for p in sorted(outdir.glob("sameprec_*")):
            txt = p.read_text().replace("GPTQ-W4", "GPTQ-W3").replace("W4 calibration", "W3 calibration")
            txt = txt.replace(str(tmpman.relative_to(ROOT)), str(MAN.relative_to(ROOT)))
            dst = S.AD.OUT / p.name.replace("sameprec_", "sameprec_w3_", 1)
            dst.write_text(txt)
            print("wrote", dst.relative_to(ROOT))
    finally:
        for p in outdir.glob("*"):
            p.unlink()
        outdir.rmdir()


if __name__ == "__main__":
    main()
