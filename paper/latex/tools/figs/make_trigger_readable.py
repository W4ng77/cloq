#!/usr/bin/env python3
"""Trigger figure without a broken axis or nominal-significance marker encoding."""
import hashlib
import json
import os
import make_figs as M
from make_figs import plt, FULL_W, INK, INK2, RESCUE, DAMAGE, REF, Line2D, Patch

def main():
    # Run every original numerical assertion; the following rendering uses the same outputs.
    M.f4()
    o = M.load("oracle")
    budgets = ["0.05", "0.1", "0.2"]
    fr = [o["frozen"][b]["pooled"] for b in budgets]
    oracle = [o["action_oracle"][b]["pooled"]["net"] for b in budgets]
    rr = [sum(c["n_escalated"]*c["R"]/c["N"] for c in o["frozen"][b]["per_cell"].values()) for b in budgets]
    rd = [sum(c["n_escalated"]*c["D"]/c["N"] for c in o["frozen"][b]["per_cell"].values()) for b in budgets]
    M.script_sha = lambda: hashlib.sha256(open(__file__,"rb").read()).hexdigest()
    fig = plt.figure(figsize=(FULL_W,3.30))
    a=fig.add_axes([.085,.26,.375,.52]); b=fig.add_axes([.61,.26,.375,.43])
    for ax in (a,b):
        M.style_axis(ax); ax.tick_params(labelsize=9,length=0,pad=4)
        ax.set_xlim(-.48,2.48); ax.set_xticks([0,1,2])
        ax.set_xticklabels([f"{x}%\n{f['n_escalated']} selected" for x,f in zip([5,10,20],fr)],fontsize=9)
        ax.axhline(0,color=INK2,lw=.7)
    fig.text(.02,.975,"(a) Capture: rescues and damages",fontsize=10,fontweight="bold",va="top")
    fig.text(.545,.975,"(b) Value: rescues minus damages",fontsize=10,fontweight="bold",va="top")
    fig.text(.02,.90,"Ordinary Q-sourced states · later nonce blocks",fontsize=8.5,color=INK2)
    fig.text(.545,.90,"No net-gain test survives Holm correction",fontsize=8.5,color=INK2)
    w=.32
    for i,f in enumerate(fr):
        for off,r,d,alpha,hatch in ((-w/2,rr[i],rd[i],.38,"///"),(w/2,f["rescued"],f["damaged"],1,None)):
            a.bar(i+off,r,w,color=RESCUE,alpha=alpha,hatch=hatch,edgecolor="white",lw=.25,zorder=2)
            a.bar(i+off,-d,w,color=DAMAGE,alpha=alpha,hatch=hatch,edgecolor="white",lw=.25,zorder=2)
        for v,dy in ((f["rescued"],.7),(-f["damaged"],-.7)):
            a.text(i+w/2,v+dy,str(abs(v)),ha="center",va="bottom" if v>0 else "top",fontsize=9)
    a.set_ylim(-15,21);a.set_yticks([-10,0,10,20],["10","0","10","20"])
    a.set_ylabel("Selected states",fontsize=9)
    a.text(-.44,13,"rescues",color=RESCUE,fontsize=8.5)
    a.text(-.44,-7,"damages",color=DAMAGE,fontsize=8.5)
    a.legend(handles=[Patch(facecolor=REF,label="Trigger"),Patch(facecolor=REF,alpha=.38,hatch="///",label="Random (expected)")],
             frameon=False,loc="upper left",bbox_to_anchor=(0,1.13),ncol=2,fontsize=8.5,handlelength=1.1,columnspacing=.9)
    vals=[f["net_gain"] for f in fr];rv=[f["random_expected_net"] for f in fr]
    b.plot([0,1,2],vals,"o-",color=INK,mfc="white",ms=5,lw=1.3)
    b.plot([0,1,2],rv,"s--",color=REF,mfc="white",ms=4.5,lw=1.1)
    for i,(v,r) in enumerate(zip(vals,rv)):
        b.annotate(f"+{v}",(i,v),xytext=(0,7),textcoords="offset points",ha="center",fontsize=9)
        b.annotate(f"+{r:.2f}",(i,r),xytext=(0,-11),textcoords="offset points",ha="center",fontsize=8.5,color=INK2)
    b.set_ylim(-.8,6.5); b.set_yticks([0,2,4,6]);b.set_ylabel("Net additional successes",fontsize=9)
    b.legend(handles=[Line2D([],[],color=INK,marker="o",mfc="white",label="Trigger"),
                      Line2D([],[],color=REF,marker="s",mfc="white",ls="--",label="Random (expected)")],
             frameon=False,fontsize=8.5,loc="upper left",bbox_to_anchor=(0,1.24),ncol=2,columnspacing=.9,handlelength=1.3)
    fig.text(.61,.84,"Matched hindsight oracle (rescues only)",fontsize=8.5,color=INK2)
    for i,v in enumerate(oracle):
        b.text(i,1.265,f"+{v}",transform=b.get_xaxis_transform(),ha="center",va="center",fontsize=9,
               bbox=dict(boxstyle="round,pad=.18",fc="#EEEEEE",ec="none"))
    pf=lambda v:f"{v:.4f}".lstrip("0")
    for ax,key in ((a,"p_turnover_ge_random"),(b,"p_net_ge_random")):
        for i,f in enumerate(fr):
            ax.text(i,-.39,f"p = {pf(f[key])}",transform=ax.get_xaxis_transform(),ha="center",fontsize=8.5,color=INK2)
    fig.text(.02,.02,"1020 states: 38 rescues, 31 damages · nominal rates; random and oracle match actual per-configuration counts",fontsize=8)
    M.save(fig,"f4_trigger_oracle",["oracle","tok"],
           "Same trigger, random, oracle and exact p-values; oracle in a numeric strip, no broken axis; all net markers neutral")
    p=os.path.join(M.OUT,"provenance.json");old=json.load(open(p))
    v=M.PROV["f4_trigger_oracle"]
    v.update(script="paper/latex/tools/figs/make_trigger_readable.py",script_sha256=M.script_sha())
    old["f4_trigger_oracle"]=v
    old.setdefault("_derived",{}).update(M.PROV_EXTRA)
    json.dump(old,open(p,"w"),indent=1,sort_keys=True)

if __name__=="__main__":
    main()
