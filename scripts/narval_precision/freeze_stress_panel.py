"""Write a deterministic Qwen3-8B RTN-W3 expansion manifest from the paper task split."""

import argparse
import hashlib
import json
from pathlib import Path

DOMAINS = {"retail": 58, "airline": 27}
PHASES = {
    "smoke": ("n26112500",),
    "qualification": tuple(f"n261125{i:02}" for i in range(1, 4)),
    "expansion": tuple(f"n261125{i:02}" for i in range(4, 24)),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    raw = args.split.read_bytes()
    split = json.loads(raw)["splits"]["dev"]["tasks"]
    tasks = {domain: sorted(map(str, split[domain])) for domain in DOMAINS}
    if any(len(set(tasks[domain])) != count or len(tasks[domain]) != count for domain, count in DOMAINS.items()):
        raise SystemExit("Expected the original 58-retail / 27-airline development panel.")

    blocks = []
    for phase, ids in PHASES.items():
        for block in ids:
            selected = tasks
            if phase == "smoke":
                selected = {
                    domain: sorted(rows, key=lambda task: hashlib.sha256(f"cloq-smoke|{domain}|{task}".encode()).digest())[:3]
                    for domain, rows in tasks.items()
                }
            blocks.append({
                "phase": phase,
                "block": block,
                "prompt_nonce": hashlib.sha256(f"cloq-precision-narval-v1|{block}".encode()).hexdigest()[:8],
                "tasks": selected,
                "run_ids": {cell: f"a6k2_q8_{cell}_{block}" for cell in ("rtn_w3", "bfpair")},
            })

    manifest = {
        "protocol": "cloq-precision-narval-v1",
        "split_sha256": hashlib.sha256(raw).hexdigest(),
        "baseline": "Qwen3-8B BF16",
        "low_precision": {"method": "RTN", "weight_bits": 3, "group_size": 128, "grid": "asymmetric"},
        "primary": "joint net success minus action-only net success on first divergent states",
        "primary_reward": "retail/airline DB success with normal termination",
        "sensitivity_reward": "official task-basis success",
        "qualification_gate": "development point estimate BF16 minus RTN-W3 >= 5 pp, full panel with matched nonces; report intervals",
        "replay_noop": {"smoke_fraction": 1, "expansion_fraction": 0.1},
        "blocks": blocks,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as file:
        json.dump(manifest, file, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
