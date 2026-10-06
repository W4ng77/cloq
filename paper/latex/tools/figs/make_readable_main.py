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
    fig = plt.figure(figsize=(FULL_W, 3.10))
    for n, (rows, x, title, sub) in enumerate([
        (A, .16, "(a) Development · W4", "85 tasks × 20 blocks · 95% intervals"),
        (H, .685, "(b) Telecom holdout", "34 tasks × 12 blocks · crossed 90%")]):
        ax = fig.add_axes([x, .24, .285, .58])
        clean(ax)
        yy = [-i - (.25 if r[-1] else 0) for i, r in enumerate(rows)]
        for r, y in zip(rows, yy):
            lab, res, dam, net = r[:4]
            ax.barh(y, -dam, height=.55, color=DAMAGE, zorder=2)
            ax.barh(y, res, height=.55, color=RESCUE, zorder=2)
            if n == 0:
                R2.ivh(ax, y, net, r[4], r[5], INK, marker="D", ms=4.5, dy=-.20)
                ax.text(1.06, y, f"{r[6]:.1f}", transform=ax.get_yaxis_transform(), fontsize=9,
                        va="center", fontweight="bold" if r[-1] else "normal")
            else:
                ax.plot(r[4], [y, y], color=INK, lw=1.4, zorder=4)
                ax.plot(net, y, "D", color=INK, mfc=INK if r[-1] else "white", ms=4.5, zorder=5)
        labs = [r[0].replace("q4", "4B").replace("q8", "8B").replace("AWQ", "AWQ-style") for r in rows]
        ax.set_yticks(yy, labs)
        for t, r in zip(ax.get_yticklabels(), rows):
            t.set_fontweight("bold" if r[-1] else "normal")
        ax.set_ylim(yy[-1]-.65, .7)
        ax.set_xlim(-14, 14); ax.set_xticks([-12, -6, 0, 6, 12])
        ax.set_xlabel("Damages ←   % of units   → Rescues", fontsize=9, labelpad=5)
        fig.text(x-.14, .975, title, va="top", fontsize=10, fontweight="bold")
        fig.text(x-.14, .89, sub, va="top", fontsize=8.5, color=INK2)
        if n == 0:
            ax.text(1.04, 1.035, "Turnover\n%", transform=ax.transAxes, fontsize=8, va="bottom")
        else:
            ax.axvspan(-3, 3, color=INK, alpha=.06, lw=0, zorder=0)
    fig.text(.02, .045, "◆ Net gain (pp)   ·   thick: fixed pool; thin: new tasks", fontsize=8.5)
    fig.text(.545, .045, "Holdout shading: frozen ±3 pp region", fontsize=8.5, color=INK2)
    M.save(fig, "f12_main_consequences", ["dev", "hconf", "ghf", "pref", "oc"],
           "Original f10 panels a/b enlarged; c/d retained in the supplementary figure; all estimates and intervals unchanged")

def references():
    pr, sa, pw, sw, dm, dg, dw, ks, margin, cp = R2.data()
    fig = plt.figure(figsize=(FULL_W, 4.65))
    def panel(pos,title,subtitle):
        ax=fig.add_axes(pos); clean(ax)
        x,y,w,h=pos
        fig.text(x-.11,y+h+.115,title,fontsize=10,fontweight="bold",va="top")
        fig.text(x-.11,y+h+.066,subtitle,fontsize=8.5,color=INK2,va="top")
        return ax
    a=panel((.13,.59,.35,.27),"(a) Same precision, different checkpoint",
            "Own first divergences · W4 · 1020 units")
    c=panel((.66,.59,.32,.27),"(b) Same operation, different tokens",
            "300 eligible q8 states · 41 tasks · exploratory")
    for y,k in zip([3,2,1],("rescue","damage","M")):
        for d,col,mk,off in ((pr,B,"o",.16),(sa,QP,"s",-.16)):
            R2.ivh(a,y+off,d[k]["est"],d[k]["ci95"],d[k]["crossed_ci95"],col,marker=mk,ms=4.5)
        for typ,col,mk,off in (("B",B,"o",.16),("K",Q,"^",-.16)):
            p=cp[k+"_"+typ];c.plot(p["widest"],[y+off]*2,color=col,lw=1.3)
            c.plot(p["est"],y+off,mk,color=col,ms=4.5)
    R2.ivh(a,0,dm["est"],dm["ci95"],dm["crossed_ci95"],INK,marker="D",ms=4.5)
    p=cp["M_KmB"];c.plot(p["widest"],[0,0],color=INK,lw=1.3);c.plot(p["est"],0,"D",color=INK,ms=4.5)
    for ax in (a,c):
        ax.set_yticks([3,2,1,0],["Rescues","Damages","Turnover","Δ turnover"])
        ax.set_ylim(-.5,3.6);ax.set_xlim(-10,24);ax.set_xticks([-5,0,5,10,15,20])
    a.axvspan(-margin,margin,ymax=.23,color=INK,alpha=.06,lw=0)
    a.set_xlabel("% of units · Δ: BF16 − Q′, pp",fontsize=9)
    c.set_xlabel("% of states · Δ: keys − BF16, pp",fontsize=9)
    handles=[Line2D([],[],color=B,marker="o",lw=1.2,label="BF16 action"),
             Line2D([],[],color=QP,marker="s",lw=1.2,label="Second checkpoint Q′"),
             Line2D([],[],color=Q,marker="^",lw=1.2,label="Key-order reversal")]
    fig.legend(handles=handles,loc="center",bbox_to_anchor=(.53,.48),ncol=3,frameon=False,fontsize=8.5,
               columnspacing=1.6,handlelength=1.3)
    b=panel((.18,.13,.64,.19),"(c) Extra BF16 action value at common states",
            "510 ordinary BF16-sourced q8 states · two-look 97% intervals")
    for y,cnt in ((1,"d1"),(0,"bf16")):
        k=ks[cnt]
        for off,key,mk,ls in ((.13,"t97","o","-"),(-.13,"boot97","s","--")):
            b.plot([100*v for v in k[key]],[y+off]*2,color=INK,lw=1.4,ls=ls)
            b.plot(100*k["point"],y+off,mk,color=INK,mfc=INK if mk=="o" else "white",ms=4.5)
        b.text(1.035,y,f"+{100*k['point']:.1f} pp",transform=b.get_yaxis_transform(),fontsize=9,va="center")
    b.set_yticks([1,0],["Q continues","B continues"]);b.set_ylim(-.5,1.5)
    b.axvspan(-margin,margin,color=INK,alpha=.06,lw=0);b.set_xlim(-6,8);b.set_xticks([-6,-3,0,3,6])
    b.set_xlabel("BF16 action − Q′ action, pp",fontsize=9)
    b.legend(handles=[Line2D([],[],color=INK,marker="o",lw=1.3,label="Block t"),
                      Line2D([],[],color=INK,marker="s",mfc="white",ls="--",lw=1.3,label="Task bootstrap")],
             frameon=False,fontsize=8.5,loc="center",bbox_to_anchor=(.52,-.50),ncol=2)
    M.save(fig,"f13_main_references",["same","w3","cs","ko"],
           "Main reference chain: same-precision turnover, common-state extra value (two-look 97%), semantic key-order reference; complete original f11 retained in appendix")

if __name__ == "__main__":
    result_one(); references(); commit_provenance()
