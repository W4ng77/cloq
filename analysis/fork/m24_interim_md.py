"""Markdown for analysis/fork/m24_interim_report.py (W100s). Every number is read from the report dict R; nothing is computed
here except 100 - exact (divergence rate). TL;DR first."""
from __future__ import annotations

DIV_KEYS = ("G", "H", "F", "GmH", "I", "offdiag", "M")
CAUSE = {("rtn_w4", "f01"): "retail:51 QB+QQ arm error (Mistral invalid function name, agent_parse_error class)",
         ("rtn_w4", "f02"): "retail:95 QQ arm error (same class)", ("gptq_w4_d1", "f01"): "airline:2 BQ arm error (empty function name)",
         ("gptq_w4_d1", "f02"): "admitted; budget_ok=false is the context-overflow sentinel (airline:45 QQ, valid failure Y=0; audit)"}


def iv(x: dict | None, k: int | None = None) -> str:
    """Primary interval; for k < 2 the block interval is degenerate, so only the crossed (task-only) interval is shown."""
    if not x:
        return "–"
    if k is not None and k < 2:
        return f"{x['est']:+.1f} (c {x['crossed_ci95'][0]:+.1f}, {x['crossed_ci95'][1]:+.1f})"
    return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"


def divr(r: dict, k: int | None) -> str:
    e = r["all_states_pp"]["exact"]
    if k is not None and k < 2:
        return f"{100 - e['est']:.1f} (c {100 - e['crossed_ci95'][1]:.1f}, {100 - e['crossed_ci95'][0]:.1f})"
    return f"{100 - e['est']:.1f} [{100 - e['ci95'][1]:.1f}, {100 - e['ci95'][0]:.1f}]"


def tau2_tables(rows: dict, label: str) -> list[str]:
    L = [f"**{label}: all states (task-equal; pp)**", "", "| cell | k | n | divergence % | r | d | M | G_all | I | off-diag | D_cc |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c, r in rows.items():
        k, a = r.get("k_blocks"), r["all_states_pp"]
        L.append(f"| {c} | {k} | {r['n_states']} | {divr(r, k)} | " + " | ".join(iv(a[s], k) for s in ("rescue", "damage", "M", "G", "I", "offdiag", "D_cc")) + " |")
    L += ["", f"**{label}: within divergent (non-exact) states (ratio; pp)**", "", "| cell | n_div | G | H | F | G−H | I | off-diag | M |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c, r in rows.items():
        k, n = r.get("k_blocks"), r.get("nonexact_pp", {})
        L.append(f"| {c} | {r['n_nonexact']} | " + " | ".join(iv(n.get(s), k) for s in DIV_KEYS) + " |")
    return L + [""]


def bfcl_table(st: dict) -> list[str]:
    L = ["| cell | items | div % | r | d | M | G_all | D_cc_all | div: G | div: H | div: F | div: G−H | div: off-diag |", "|---" * 13 + "|"]
    for c, r in st["cells"].items():
        a, d = r["all_items_pp"], r["cond_div_pp"]
        L.append(f"| {c} | {r['n_items']} | {100 * r['n_div'] / r['n_items']:.1f} | " + " | ".join(iv(a[s]) for s in ("rescue", "damage", "M", "G", "D_cc"))
                 + " | " + " | ".join(iv(d.get(s)) for s in ("G", "H", "F", "GmH", "offdiag")) + " |")
    return L + [""]


def render(R: dict, jp) -> str:
    m, q = R["m24"], R["q8_reference"]
    P, AV, CC = m["primary"], m["available_rows"], m["complete_case"]
    g, rr = P["gptq_w4_d1"], P["rtn_w4"]
    M1, mb = m["M1"], m["bfcl"]
    s = M1["available_rows_sensitivity"]["D_cc"]
    gmh = lambda r: r["nonexact_pp"]["GmH"]  # noqa: E731
    L = [f"# m24 (Mistral-Small-3.2-24B) new-method panel: phase-1 INTERIM analysis ({R['utc']})", "",
         "**TL;DR** INTERIM: phase 1 only (f01–f03); phase 2 (f04–f06) is running. This is not the protocol's final m24 analysis, "
         "and none of these numbers is a paper claim yet.",
         f"- **Admission (A3.3, strict on the 83-task population).** rtn_w4 admits {', '.join(R['admission']['admitted']['rtn_w4'])}; "
         f"gptq_w4_d1 admits {', '.join(R['admission']['admitted']['gptq_w4_d1'])}. This matches the two-skeptic budget audit. "
         "Three fork-branch Mistral parse errors (Y = None, never imputed) fail rtn f01, rtn f02 and gptq f01. "
         "gptq f02's `budget_ok=false` is the context-overflow sentinel, a valid failure, so the block is admitted.",
         f"- **τ² primary per cell.** Divergence: gptq {divr(g, 2)} %, rtn {divr(rr, 1)} %. "
         f"Turnover M: gptq {iv(g['all_states_pp']['M'], 2)}, rtn {iv(rr['all_states_pp']['M'], 1)} pp. "
         f"Net G_all: gptq {iv(g['all_states_pp']['G'], 2)}, rtn {iv(rr['all_states_pp']['G'], 1)} pp. "
         f"Within-divergent G−H: gptq {iv(gmh(g), 2)}, rtn {iv(gmh(rr), 1)} pp. "
         "With k = 2 (t, df 1) and k = 1 (crossed task-only interval), the primary resolves nothing about G−H.",
         f"- **M1 (gptq_w4_d1 − rtn_w4, D_cc).** The primary is not estimable: {M1['primary']['not_estimable']} "
         f"(f03), and §7 gives no fallback. The f03 point estimate is {M1['common_block_descriptive']['d_D_cc_pp']:+.1f} pp "
         f"(n = {M1['common_block_descriptive']['n_states']}, descriptive). In the available-rows sensitivity (k = 3), "
         f"ΔD_cc is {s['est']:+.1f} [{s['ci95'][0]:+.1f}, {s['ci95'][1]:+.1f}] pp (t, p = {s['t_p_two_sided']:.3f}).",
         f"- **Sensitivities with k = 3 (labelled).** Within-divergent G−H on the available rows: "
         f"gptq {iv(gmh(AV['gptq_w4_d1']))}, rtn {iv(gmh(AV['rtn_w4']))} pp. Complete-case: gptq {iv(gmh(CC['gptq_w4_d1']))}, "
         f"rtn {iv(gmh(CC['rtn_w4']))} pp.",
         f"- **BFCL (complete; 200 items; no phase 2).** Within-divergent G−H: gptq {iv(mb['cells']['gptq_w4_d1']['cond_div_pp']['GmH'])}, "
         f"rtn {iv(mb['cells']['rtn_w4']['cond_div_pp']['GmH'])} pp. M1 D_cc_all is {iv(mb['contrasts']['M1']['D_cc'])} pp "
         f"(item bootstrap p = {mb['contrasts']['M1']['D_cc']['boot_p_two_sided']:.2f}).",
         f"- **q8 W4 reference, same protocol (descriptive, never pooled).** τ² within-divergent G−H: "
         f"gptq {iv(gmh(q['tau2']['gptq_w4_d1']))}, awq {iv(gmh(q['tau2']['awq_w4']))} pp, with k = 3. "
         f"BFCL: gptq {iv(q['bfcl']['cells']['gptq_w4_d1']['cond_div_pp']['GmH'])}, "
         f"awq_d1 {iv(q['bfcl']['cells']['awq_w4_d1']['cond_div_pp']['GmH'])} pp. "
         "The paper's significant q8 G−H (+2.9 and +3.4) comes from first-divergence states with 20 blocks, not from this panel.",
         f"- **Local fidelity (§9):** {m['fidelity']['status']}.", "", "**Reading (paper question).** " + (R.get("reading") or "–"), "",
         "## 1. Admission", "", "| cell | block | complete / 83 | admitted | reason |", "|---|---|---|---|---|"]
    for c, v in R["admission"]["blocks"].items():
        for b, x in v.items():
            L.append(f"| {c} | {b} | {x['complete']} | {x['admitted']} | {CAUSE.get((c, b), '')} |")
    L += ["", f"Audit: `{R['admission']['audit']}` (budget_ok mechanism, the overflow sentinel, and the arm errors). "
          "Whether a fork-branch `agent_parse_error` should count as Y = 0, as overflow does, is an open rule. "
          "It needs a dated, disclosed amendment from the main session, and it is not applied here.", "",
          "## 2. τ² strict primary (83-task conditional population, A3)", "",
          "Intervals: gptq_w4_d1 has k = 2, so the primary is t over 2 block means (df 1). Zero-width intervals there "
          "(H, F, D_cc, off-diag, exact) mean the two block means are identical (see §3), not that the estimate is precise. "
          "rtn_w4 has k = 1: the block bootstrap is degenerate and t is undefined, so `c (lo, hi)` is the crossed interval, "
          "which here only resamples tasks within f03.", ""]
    L += tau2_tables(P, "Primary")
    L += ["## 3. Per-block values (descriptive; pp)", "", "| set | cell | block | n | n_div | div: G | div: H | div: F | div: G−H | div: off-diag | div: M | all: D_cc |",
          "|---" * 12 + "|"]
    for lab, pb in (("primary", m["per_block"]), ("available rows", m["per_block_available"])):
        for c, v in pb.items():
            for b, x in v.items():
                d = x["div"]
                L.append(f"| {lab} | {c} | {b} | {x['n']} | {x['n_nonexact']} | " + " | ".join(f"{d[k]:+.1f}" for k in ("G", "H", "F", "GmH", "offdiag", "M")) + f" | {x['all']['D_cc']:+.1f} |")
    cb, ad = M1["common_block_descriptive"], M1["available_rows_descriptive"]
    L += ["", "## 4. M1 = gptq_w4_d1 − rtn_w4 (the only m24 primary contrast; Holm over one = unadjusted)", "",
          f"- **Primary (τ² D_cc, t over block-mean differences, blocks complete in both cells):** not estimable, "
          f"{M1['primary']['not_estimable']} {M1['primary']['common_blocks']}.",
          f"- **Common block, descriptive point estimates only** ({cb['blocks']}, n = {cb['n_states']}): ΔD_cc {cb['d_D_cc_pp']:+.1f}, "
          f"ΔG {cb['d_G_pp']:+.1f}, Δ(G−H) {cb['d_GmH_pp']:+.1f}, ΔM {cb['d_M_pp']:+.1f}, ΔM_cc {cb['d_M_cc_pp']:+.1f} pp.",
          f"- **Available-rows sensitivity** (labelled; blocks {M1['available_rows_sensitivity']['common_blocks']}, "
          f"n = {M1['available_rows_sensitivity']['n_states']} paired states): " +
          "; ".join(f"Δ{k} {iv(M1['available_rows_sensitivity'][k])} (t p {M1['available_rows_sensitivity'][k]['t_p_two_sided']:.3f}; "
                    f"block bootstrap [{M1['available_rows_sensitivity'][k]['block_boot_ci95'][0]:+.1f}, {M1['available_rows_sensitivity'][k]['block_boot_ci95'][1]:+.1f}])"
                    for k in ("D_cc", "G", "M", "M_cc")) + ". Block bootstrap and t disagree, which is expected with 3 blocks; t is primary.",
          f"- Δ(G−H) on the available rows (descriptive): {ad['d_GmH_pp']:+.1f} pp.",
          f"- **BFCL M1 (D_cc_all, item-paired, {mb['contrasts']['M1']['n_items']} items):** {iv(mb['contrasts']['M1']['D_cc'])}, "
          f"p = {mb['contrasts']['M1']['D_cc']['boot_p_two_sided']:.2f}; ΔG {iv(mb['contrasts']['M1']['G'])}; ΔM {iv(mb['contrasts']['M1']['M'])}.", "",
          "## 5. Sensitivities (labelled; not the primary)", ""]
    L += tau2_tables(CC, "Complete-case on the 83-task population (any block)")
    L += tau2_tables(AV, "Actual available rows (no mask, no strictness; includes airline:13 in f02–f03)")
    L += ["## 6. BFCL panel B (200 items, 50 per category; complete, no expansion)", "",
          "Each cell's own first-divergence states on the same items; all-item quantities count no-divergence items as 0; "
          "intervals: item bootstrap within category (describes item sampling only). BF16 floor passed (A2.2: 40/200).", ""]
    L += bfcl_table(mb)
    L += ["## 7. Qwen3-8B (q8) W4 reference cells under the same protocol (descriptive; never pooled)", "", q["label"], ""]
    L += tau2_tables(q["tau2"], "q8 τ² (85 tasks)")
    L += tau2_tables(q["tau2_on_m24_83_tasks_descriptive"], "q8 τ² restricted to the m24 83 tasks (descriptive)")
    L += ["**q8 BFCL W4 reference (same 200 items)**", ""] + bfcl_table(q["bfcl"])
    L += [f"Paper context (not this panel): {R['paper_context']['label']}: q8 within-divergent G−H "
          f"gptq {R['paper_context']['q8_GmH_div_pp']['gptq_w4_d1']}, awq {R['paper_context']['q8_GmH_div_pp']['awq_w4']} "
          f"(`{R['paper_context']['source']}`).", "",
          "## 8. Caveats", "",
          "- INTERIM. Phase 2 (f04–f06) will add up to 3 blocks per cell. The final protocol analysis (`analyze_newmethod.py --model m24`, "
          "all admitted blocks) supersedes every number here. Nothing here was used to make any decision.",
          "- G−H (= Y_BQ − Y_QB) is not a §4 estimand of this protocol. It is added for the paper's question, with the same Boot, seed and ratio "
          "form as G/H/F. Per-block values, the M1 point estimates and the q8 83-task view are also additions. Every protocol field is recomputed and asserted "
          "equal to the protocol runs' JSON.",
          "- The available-rows sensitivity drops the errored states (Mistral parse errors), so it is not missing-at-random. It also adds airline:13 "
          "outside the A3 population. The complete-case analysis keeps the population but mixes blocks of different completeness.",
          "- m24 estimates describe the 83-task conditional population (A3.2). The q8 reference states lie on q8's own BF16 trajectory, so the "
          "states differ even where the tasks are equal. The comparison is descriptive and nothing is pooled.",
          "- BFCL states are each cell's own first divergences on the same items. Cross-cell BFCL contrasts compare items, not states.",
          "- Local fidelity (§9; KLu, exact-agreement strata, KL tertiles) is pending, because the m24 score outputs on disk are the failed pre-fix runs.", "",
          "## 9. Provenance", "", f"- Report script `analysis/fork/m24_interim_report.py` sha `{R['script_sha256'][:12]}`, git `{R['git'][:10]}`, "
          f"B = {R['B']}, seed {R['seed']}. The script recomputes every protocol field it prints and asserts equality with the protocol runs' JSON.",
          *[f"- `{p}` sha256 `{h[:16]}…`" for p, h in R["inputs"].items()],
          f"- Guards: protocol `{R['guard']['m24']['protocol_sha256'][:12]}`, m24 manifest `{R['guard']['m24']['manifest_sha256'][:12]}`, "
          f"mask `{R['guard']['m24']['mask_sha256'][:12]}`, q8 manifest `{R['guard']['q8']['manifest_sha256'][:12]}`.",
          f"- Full numbers (crossed intervals, block bootstrap, 16 patterns, (Δ_Q, Δ_B) tables): `{jp}`.", ""]
    return "\n".join(L)
