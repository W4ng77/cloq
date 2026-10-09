#!/usr/bin/env python3
"""Readable main-text figures; numerical assertions reused from the original figures."""
import hashlib
import json
import os
import make_figs as M
import make_fig_r1quad as R1
import make_fig_r2quad as R2
from make_figs import plt, FULL_W, B, Q, QP, INK, INK2, RESCUE, DAMAGE, Line2D

M.SRC.update(same="analysis/fork/out/sameprec_20261004T070601Z.json",
             w3="analysis/fork/out/sameprec_w3_20261004T070607Z.json",
             cs="analysis/fork/out/commonstate_q8ext_20261003T231159Z.json",
             ko="analysis/fork/out/keyorder_20261005T204349Z.json",
             pref="analysis/fork/out/pattern_ref_20261005T134721Z.json",
             oc="analysis/fork/out/outcome_classes_20261004T143614Z.json")
M.script_sha = lambda: hashlib.sha256(open(__file__, "rb").read()).hexdigest()

def commit_provenance():
    p = os.path.join(M.OUT, "provenance.json")
    old = json.load(open(p))
    for name, v in M.PROV.items():
        v.update(script="paper/latex/tools/figs/make_readable_main.py", script_sha256=M.script_sha())
        old[name] = v
    json.dump(old, open(p, "w"), indent=1, sort_keys=True)

def clean(ax):
    M.style_axis(ax, grid_axis="x")
    ax.tick_params(labelsize=9, length=0, pad=3)
    ax.axvline(0, color=INK2, lw=.7, zorder=1)

def result_one():
    A, H, _, _ = R1.data()
    ghf = M.load("ghf")
    fig = plt.figure(figsize=(FULL_W, 4.65))
    for n, (rows, x, title, sub) in enumerate([
        (A, .16, "(a) Development · W4", "Full task pool · 95% intervals"),
        (H, .66, "(b) Telecom holdout · 90%", "Full task pool · crossed intervals")]):
        ax = fig.add_axes([x, .49, .25, .36]); clean(ax)
        yy = [-i - (.25 if r[-1] else 0) for i, r in enumerate(rows)]
        for r, y in zip(rows, yy):
            lab, res, dam, net = r[:4]
            ax.barh(y, -dam, height=.55, color=DAMAGE, hatch="///", edgecolor="white", lw=.2, zorder=2)
            ax.barh(y, res, height=.55, color=RESCUE, zorder=2)
            if n == 0:
                ax.plot(r[5], [y, y], color=INK, lw=1.4, zorder=4)
                ax.plot(net, y, "D", color=INK, ms=6 if r[-1] else 4.5, zorder=5)
                turnover = r[6]
            else:
                ax.plot(r[4], [y, y], color=INK, lw=1.4, zorder=4)
                ax.plot(net, y, "D", color=INK, ms=6 if r[-1] else 4.5, zorder=5)
                turnover = res + dam
            ax.text(1.065, y, f"{turnover:.1f}", transform=ax.get_yaxis_transform(), fontsize=9,
                    va="center", fontweight="bold" if r[-1] else "normal")
        labs = [r[0].replace("q4", "4B").replace("q8", "8B").replace("AWQ", "AWQ-style") for r in rows]
        ax.set_yticks(yy, labs)
        for label, r in zip(ax.get_yticklabels(), rows):
            label.set_fontweight("bold" if r[-1] else "normal")
        ax.set_ylim(yy[-1]-.65, .7); ax.set_xlim(-14, 14); ax.set_xticks([-12,-6,0,6,12])
        ax.set_xlabel("Damages ←   % of units   → Rescues", fontsize=9, labelpad=5)
        fig.text(x-.14, .98, title, va="top", fontsize=10, fontweight="bold")
        fig.text(x-.14, .918, sub, va="top", fontsize=8.5, color=INK2)
        ax.text(1.04, 1.035, "Turnover\n%", transform=ax.transAxes, fontsize=8, va="bottom")
        if n: ax.axvspan(-3,3,color=INK,alpha=.06,lw=0,zorder=0)
    fig.text(.02,.395,"◆ Full-pool net gain · new-task 95% intervals",fontsize=8.5)
    fig.text(.55,.395,"Holdout shading: frozen ±3 pp region",fontsize=8.5,color=INK2)
    fig.text(.02,.34,"(c) All three modes on divergent states",fontsize=10,fontweight="bold")
    fig.text(.02,.301,"Separate denominator · equal-weight pools · new-task 95% intervals",fontsize=8.5,color=INK2)
    for x,pool,name,nstates in ((.20,"W4:all","W4",5576),(.69,"KV8:all","KV8",1448)):
        if pool not in ghf["pools"]:
            pool = "KV8:all" if "KV8:all" in ghf["pools"] else "KV8"
        ax=fig.add_axes([x,.110,.22,.125]); clean(ax)
        stats=ghf["pools"][pool]["stats"]
        for y,mode in zip([2,1,0],"GHF"):
            q=stats[mode]; ci=q["crossed_ci95"]
            ax.plot(ci,[y,y],color=B,lw=1.4); ax.plot(q["est"],y,"o",color=B,ms=4.5)
            ax.text(1.06,y,f"{q['est']:+.1f}",transform=ax.get_yaxis_transform(),fontsize=9,va="center")
        ax.set_yticks([2,1,0],["G · action","H · continuation","F · both"])
        ax.set_xlim(-6,6);ax.set_xticks([-6,-3,0,3,6]);ax.set_ylim(-.5,2.5)
        ax.set_xlabel("Net gain on divergent states (pp)",fontsize=8.5,labelpad=3)
        ax.text(.5,1.12,f"{name} pool · {nstates:,} states",transform=ax.transAxes,ha="center",fontsize=9,fontweight="bold")
    M.save(fig,"f12_main_consequences",["dev","hconf","ghf","pref","oc"],
           "Full-pool action-only rates and divergent-state G/H/F shown separately; unchanged outputs, new-task 95% for the promoted mode panel")

def references():
    pr, sa, pw, sw, dm, dg, dw, ks, margin, cp = R2.data()
    fig = plt.figure(figsize=(FULL_W, 3.0))
    def panel(pos,title,subtitle):
        ax=fig.add_axes(pos); clean(ax)
        x,y,w,h=pos
        fig.text(x-.11,y+h+.115,title,fontsize=10,fontweight="bold",va="top")
        fig.text(x-.11,y+h+.066,subtitle,fontsize=8.5,color=INK2,va="top")
        return ax
    a=panel((.13,.26,.35,.49),"(a) Same precision, different checkpoint",
            "Own first divergences · W4 · 1020 units")
    c=panel((.66,.26,.32,.49),"(b) Same operation, different tokens",
            "300 eligible q8 states · 41 tasks · exploratory")
    for y,k in zip([3,2,1],("rescue","damage","M")):
        for d,col,mk,off in ((pr,B,"o",.16),(sa,QP,"s",-.16)):
            a.plot(d[k]["crossed_ci95"], [y+off]*2, color=col, lw=1.3)
            a.plot(d[k]["est"],y+off,mk,color=col,ms=4.5)
        for typ,col,mk,off in (("B",B,"o",.16),("K",Q,"^",-.16)):
            p=cp[k+"_"+typ];c.plot(p["widest"],[y+off]*2,color=col,lw=1.3)
            c.plot(p["est"],y+off,mk,color=col,ms=4.5)
    a.plot(dm["crossed_ci95"], [0,0], color=INK, lw=1.3)
    a.plot(dm["est"],0,"D",color=INK,ms=4.5)
    p=cp["M_KmB"];ci=[-p["widest"][1],-p["widest"][0]]
    assert [round(v,1) for v in ci] == [-2.9,8.4]
    c.plot(ci,[0,0],color=INK,lw=1.3);c.plot(-p["est"],0,"D",color=INK,ms=4.5)
    for ax in (a,c):
        ax.axhline(.5,color=INK2,lw=.6,ls="--",alpha=.6)
        ax.set_yticks([3,2,1,0],["Rescues","Damages","Turnover","Δ turnover"])
        ax.set_ylim(-.5,3.6);ax.set_xlim(-10,24);ax.set_xticks([-5,0,5,10,15,20])
    a.axvspan(-margin,margin,ymax=.23,color=INK,alpha=.06,lw=0)
    a.set_xlabel("% of units · Δ: BF16 − Q′, pp",fontsize=9)
    c.set_xlabel("% of states · Δ: BF16 − keys, pp",fontsize=9)
    handles=[Line2D([],[],color=B,marker="o",lw=1.2,label="BF16 action"),
             Line2D([],[],color=QP,marker="s",lw=1.2,label="Second checkpoint Q′"),
             Line2D([],[],color=Q,marker="^",lw=1.2,label="Key-order reversal")]
    fig.legend(handles=handles,loc="center",bbox_to_anchor=(.53,.055),ncol=3,frameon=False,fontsize=8.5,
               columnspacing=1.6,handlelength=1.3)

    M.save(fig,"f13_main_references",["same","w3","cs","ko"],
           "Main references: same-precision and semantic key-order turnover; new-task 95% only for same-precision. Full adjusted common-state values retained in appendix")

if __name__ == "__main__":
    result_one(); references(); commit_provenance()
