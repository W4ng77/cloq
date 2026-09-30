# Resource plan — nodes, GPUs, simulator replicas, agent slots (W34-infra)

**TL;DR** 38 A6000s are held by CLOQ runners right now (not 42: node006's job holds 4 cards, because another user holds
the other 4). The user simulator (Qwen3-30B-A3B-Instruct-2507, TP=2 on one NVLink pair, canary `9a594b881feb752a`)
is now at **6 live replicas (12 GPUs)**, up from 5. The 6th, node004-8007, was added as a `kind: sim` queue task, with no
runner restart and no interrupted episode. The 7th (node005, `sim_node005_r2`) is parked in `queue/deferred/`: simulator
waiting is 0–6 cluster-wide, below the §3 rule (add only when waiting stays above 30 for 30 min). Requeue that task
file when the rule fires; it drains a pair and starts on its own. Every replica is listed in the instance registry
(`/data/ziyangs/cloq_work/sims/<node>-<port>.json`), and the balancer routes new runs by instance URL.
Rollout status and evidence: §4 and `docs/RESEARCH_LOG.md` W34-infra.

## 1 Inventory (measured 2026-09-29 22:00 PDT)

| Node | Runner job | GPUs held (job-local idx) | Cores (job / node) | RAM (node) | Runner flags | Simulator replicas | Agent GPUs |
|---|---|---|---|---|---|---|---|
| node001 | 49670 | 4 (0–3) | 16 / 48 | 755 GB | `--max-gpus-per-task 1` | 1: GPUs 0,1 :8000 | 2 (1-GPU tasks only) |
| node003 | 49694 | 6 (1–6; GPUs 0 [PCI 01:00.0] and 7 [E1:00.0] fail the probe) | 32 / 48 | 755 GB | `--sim-gpus '' --max-gpus-per-task 1` | none (routed) | 6 (1-GPU only) |
| node004 | 49671 | 8 (0–7) | 32 / 48 | 755 GB | default | **2**: 0,1 :8000 + 6,7 :8007 (sim task `sim_node004_r2`) | 4 |
| node005 | 49672 | 8 (0–7) | 32 / 48 | 755 GB | default | 1: 0,1 :8000 (2nd replica deferred, ready to requeue) | 6 |
| node006 | 49642 | 4 (0–3) | 32 / 48 | 755 GB | default | 1: 0,1 :8000 | 2 |
| node007 | 49673 | 8 (0–7) | 16 / 48 | 755 GB | default | 1: 0,1 :8000 | 6 |
| **Total** | 6 jobs | **38** | 160 | — | — | **6 now (12 GPUs); 7 planned (14)** | **26 now; 24 at 7 replicas** (+ packing, §3) |

- Nodes not held: node002 and node008. Our jobs 49599/49600 there are pending (Resources): all 48 cores are taken by
  CPU-only jobs of other users. node009 has bad cards and is excluded.
- GPU: RTX A6000 with 46–48 GB. NVLink (NV4) links only the pairs (0,1)(2,3)(4,5)(6,7). Other pairs go over PCIe/NUMA
  (NODE/SYS in `nvidia-smi topo -m`), so TP=2 runs only on NVLink pairs (W4).
- RAM is 755 GB per node (`free -g`), not the 512 GB in older notes. `--mem` is not enforced. Node-local `/tmp` is
  RAM-backed and holds the checkpoints that are being built.
- One Slurm job per node (the epilog kills same-user processes, see the cluster memory note). Anything more that runs on
  a node is either a step inside the runner job (`srun --jobid --overlap`, e.g. gpumon) or a queue task that the runner
  starts.

## 2 Simulator layout and ports

| Item | Rule |
|---|---|
| Replica model | q30a3 (`Qwen/Qwen3-30B-A3B-Instruct-2507` @ `0d7cf239…`), served name `user`, max_len 65 536, TP=2, `GPU_UTIL` 0.90, frozen numerics (`env.sh`: batch invariant, `TORCHINDUCTOR_DETERMINISTIC=1`) |
| Numerics gate | Each replica must reproduce `analysis/determinism/canary_sim_q30a3.json` (hash `9a594b881feb752a`). A new replica must also give identical answers to identical requests as a live reference replica: 4 simulator-style prompts, greedy decoding, token ids and exact top-5 logprobs compared (`simreg.noop_check`). |
| Ports | Replica 1: :8000. A replica started by a runner with `--sims N`: :8000+k (the runner refuses a port that equals 8001+g for an agent card g). A replica started by a sim task: :8001+first GPU (8003/8005/8007), which is the port the runner reserves for that pair anyway. Agent servers: 8001+g. Fork B/Q servers: +100/+200. |
| Registry | `cloq_work/sims/<node>-<port>.json`, written only by the owner: the runner (`owner.kind=runner`), the sim task (`sim_task`), or `simreg.py adopt` for replicas started by pre-registry runners (`adopted`; the balancer refreshes their health). |
| States | starting → up → draining → stopped, or dead. Only an `up` replica whose health record is < 660 s old gets new routes. |
| Routing | `sim_balancer.py`, every 5 min, per-instance load = waiting + 0.1·running + 20·max(0, KV − 0.8). It rewrites `queue/USER_BASE.<node>` atomically. worker.py reads that file at each run start and ignores a route to a replica that is not live. A route to a non-live replica is moved at once; otherwise there is a 15-min hold per node, and each pass adds +BUSY/2 to the target's expected load (no herding). |
| Episode safety | A run keeps its simulator URL for its whole life. Every run_arm/fork_driver holds a lease (`cloq_work/sims/leases/`, refreshed every 10 s). A draining replica stops only after all its leases are gone. If it is forced to stop (Slurm job end, crash), it records the leases (run ids) in `logs/sim_interruptions.jsonl` and in the registry. The worker's W6 guard then fails the affected run as an outage, and the run resumes via tau2 auto_resume. Finished episodes are kept and never duplicated. |
| Monitoring | `gpumon.sh` samples ports 8000–8010 plus every registered port of the node (`"sim":1`). `gputop.py` labels replicas by registry state and prints one line per replica. `python scripts/a6000/simreg.py list` shows state, health and leases. |

## 3 Agent slots and allocation after the expansion

- Agent GPUs: 38 − 12 = 26 cards now (28 before), and 24 once the 7th replica is added. node003 (6) and node001 (2) take 1-GPU tasks only; node004/005/007
  keep NVLink pairs for TP=2 tasks.
- q4 agents are packed two per card where the queue asks for it (EXECUTION_PLAN §3). Each server still has to pass its
  canary.
- Simulator demand check (EXECUTION_PLAN §4.2): add a replica when cluster-wide waiting stays above 30 for more than
  30 min. Take a replica back when all replicas are idle, by writing `simreg.py retire <id>`: it drains, then stops once
  its leases are gone, and the runner reuses the pair.

## 4 Rollout procedure (drain-then-add, no all-node restart)

1. **Registry first.** `simreg.py adopt` registers the 5 running :8000 replicas after a live canary check. All 5 match
   the reference `9a594b881feb752a`. The balancer is then restarted with instance routing. This is a login-node process;
   no job is touched.
2. **Drain by queue, not by kill.** Queue a pinned task `{"kind": "sim", "gpus": 2, "node": "<node>", "priority": -100}`.
   While a 2-GPU task waits, the running runner already keeps its upper NVLink pairs for 2-GPU tasks (W5): a card that
   frees up is not refilled with a 1-GPU task. The pair therefore empties as its valid tasks finish, and the sim task
   (highest priority) claims it. No task is killed and no episode is interrupted. New runners also accept an explicit
   `queue/DRAIN.<node>` (a GPU list): drained cards take only the sim task.
3. **Validate before serving.** The sim task (`worker.py run_sim`) starts vLLM on 0.0.0.0, checks the canary against
   the fixed reference, runs the identical-request check against the node's :8000 replica, and runs a concurrent
   throughput probe (16 requests). Only then does it write `state: up`. Any failure marks it `dead`, the task goes to
   `failed/`, and the runner gets the pair back.
4. **Route.** The balancer sends a node's next runs to the new replica when the current one is busy, or to split the
   load between two local replicas. Check live load with gputop and `gpumon/<node>.jsonl`.
5. **Then the next node.** Only after step 4 is verified on node004 is the second sim task queued for node005.
6. **Runner restarts** (only if ever needed, e.g. to use `--sims 2` from the start): one node at a time, after
   `STOP.<node>` has let the node drain. Submit held with the existing pattern
   (`sbatch --hold -w <node> --gres=gpu:A6000:8 -c 32 scripts/a6000/node.sbatch --sim-gpus 0,1 --sim-model q30a3 --sims 2`),
   check that no other job of the user is on the node, release, and record the job ids in RESEARCH_LOG. Not needed for
   this rollout.

## 5 Rollout record (2026-09-29 PDT)

| Time | Step | Evidence |
|---|---|---|
| 21:5x | Code committed (d8a7d27, 51d5cc7, f7f4e9c). Dry run with fake servers: 17/17 checks pass | `scripts/a6000/dryrun_simreg.py`, `/data/ziyangs/cloq_work/logs/w34_infra_dryrun.txt` |
| 21:5x | Live checks before any change: canary of all 5 replicas from the login node (under load) = `9a594b881feb752a`; no-op node007 vs node006 4/4 identical | `simreg.py adopt` output (§4 step 1) |
| 22:02 | 5 replicas adopted into the registry; balancer restarted with instance routing (old pid 462778 → 476851) | `cloq_work/sims/node00*-8000.json`, `logs/sim_balancer.log` |
| 22:02 | `sim_node004_r2` queued. The runner (job 49671, not restarted) held GPU 7 idle for 2-GPU work until GPU 6's `fork_accept_kv16_bridge_q4` finished normally | `logs/node_node004_49671.out` |
| 22:11 | Claimed on GPUs 6,7 (port 8007) | same |
| 22:14 | Up: canary `9a594b881feb752a` = reference; no-op vs node004-8000 4/4 identical; 16-way probe 377.6 gen tok/s | `cloq_work/sims/node004-8007.json`, `logs/sim_instances.log`, `logs/canary.log` |
| 22:14 | node004's new runs routed to node004-8007 (manual, logged). By 22:35 it holds 8 run leases | `logs/sim_balancer.log`, `simreg.py list` |
| 22:23 | Under a 32-way concurrent load: no-op vs node004-8000 4/4 identical; 618.4 gen tok/s (p50 19.8 s for 384 tokens) | `logs/w34_node004-8007_noop_underload.json`, `logs/w34_node004-8007_tp32.json` |
| 22:24 | `sim_node005_r2` queued, then deferred by the main session at 22:35 (demand rule not met) | `queue/deferred/sim_node005_r2.json` |

No runner was restarted, and no Slurm job was submitted or cancelled. No episode was interrupted
(`logs/sim_interruptions.jsonl` does not exist). Runs started before d8a7d27 hold no leases; they are on the :8000
replicas, which this rollout did not touch.
