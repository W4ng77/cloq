#!/usr/bin/env python3
"""Complement the main figures without repeating their development/holdout or semantic-reference panels."""
import make_readable_main as main
import make_figs as M
import make_fig_r1quad as R1
import make_fig_r2quad as R2
from make_figs import plt, FULL_W, B, QP, INK, INK2, Line2D
import hashlib
import json
import os

M.script_sha = lambda: hashlib.sha256(open(__file__, 'rb').read()).hexdigest()

def patterns():
    _, _, _, rows = R1.data()
    fig=plt.figure(figsize=(FULL_W,2.5))
    for i,typ in enumerate(('J','U')):
        x=.16+.50*i
        ax=fig.add_axes([x,.24,.28,.52]); main.clean(ax)
        selected=[r for r in rows if r[0]==typ]
        for y,r in zip([2,1,0],selected):
            _,lab,obs,ref,est,fx,cr=r
            R2.ivh(ax,y,est,fx,cr,INK,ms=4.5,dy=-.15)
            ax.text(1.07,y,f'{obs:.1f} / {ref:.1f}',transform=ax.get_yaxis_transform(),va='center',fontsize=9)
        ax.set_yticks([2,1,0],['W4 pool','4B','8B']);ax.set_ylim(-.5,2.5)
        ax.set_xlim(-3.1,3.1);ax.set_xticks([-3,0,3]);ax.set_xlabel('Observed − permutation reference (pp)',fontsize=9)
        ax.text(1.04,1.08,'Obs. / ref. %',transform=ax.transAxes,fontsize=8.5)
        fig.text(x-.14,.97,('(a) Joint rescue' if i==0 else '(b) Rescue undone'),fontsize=10,fontweight='bold',va='top')
    fig.text(.02,.055,'Divergent-state shares · exploratory · thick: fixed-pool 95%; thin: new-task 95%',fontsize=9,color=INK2)
    M.save(fig,'f14_pattern_reference',['ghf','pref','oc'],'Observed joint-rescue and rescue-undone shares minus their label-permutation references; complements main G/H/F panel')

def reference_details():
    pr,sa,pw,sw,_,_,_,K,margin,_=R2.data()
    fig=plt.figure(figsize=(FULL_W,4.1))
    a=fig.add_axes([.17,.60,.26,.24]);main.clean(a)
    fig.text(.02,.97,'(a) W3 stress: turnover',fontsize=10,fontweight='bold',va='top')
    fig.text(.02,.905,'510 units · three blocks · own first divergences',fontsize=8.5,color=INK2)
    for y,p,col,mk in ((1,pw,B,'o'),(0,sw,QP,'s')):
        q=p['M'];R2.ivh(a,y,q['est'],q['ci95'],q['crossed_ci95'],col,marker=mk,ms=4.5)
    a.set_yticks([1,0],['BF16','Second W3']);a.set_ylim(-.6,1.6);a.set_xlim(0,32);a.set_xticks([0,10,20,30]);a.set_xlabel('Turnover (% of units)',fontsize=9)
    b=fig.add_axes([.65,.60,.27,.24]);main.clean(b)
    fig.text(.535,.97,'(b) Continuation-dependent share',fontsize=10,fontweight='bold',va='top')
    fig.text(.535,.905,'Own divergent states · descriptive',fontsize=8.5,color=INK2)
    for y,(p,s) in zip([1,0],((pr,sa),(pw,sw))):
        for off,t,col,mk in ((.15,p,B,'o'),(-.15,s,QP,'s')):
            q=t['cond_offdiag'];R2.ivh(b,y+off,q['est'],q['ci95'],q['crossed_ci95'],col,marker=mk,ms=4.5)
    b.set_yticks([1,0],['W4','W3']);b.set_ylim(-.6,1.6);b.set_xlim(8,46);b.set_xticks([10,20,30,40]);b.set_xlabel('% of divergent states',fontsize=9)
    fig.legend(handles=[Line2D([],[],color=B,marker='o',lw=1.3,label='BF16 substitute'),Line2D([],[],color=QP,marker='s',lw=1.3,label='Same-precision substitute')],loc='center',bbox_to_anchor=(.53,.475),frameon=False,ncol=2,fontsize=9)
    fig.text(.02,.395,'(c) Common states: full interval display',fontsize=10,fontweight='bold')
    fig.text(.02,.345,'510 ordinary BF16-sourced 8B states · two-look 97%; unadjusted 95% shown below each line',fontsize=8.5,color=INK2)
    c=fig.add_axes([.24,.10,.57,.19]);main.clean(c)
    labels=[]
    for base,cnt in ((3,'d1'),(1,'bf16')):
        q=K[cnt]
        for off,th,tn,mk in ((.22,'t97','t95','o'),(-.22,'boot97','boot95','s')):
            y=base+off
            c.plot([100*v for v in q[th]],[y]*2,color=INK,lw=1.6)
            c.plot([100*v for v in q[tn]],[y-.13]*2,color=INK,lw=.6)
            c.plot(100*q['point'],y,mk,color=INK,ms=4)
            labels.append((y,('Q continues' if cnt=='d1' else 'B continues')+' · '+('block t' if mk=='o' else 'bootstrap')))
    c.set_yticks([y for y,_ in labels],[s for _,s in labels],fontsize=8.5)
    c.axvspan(-margin,margin,color=INK,alpha=.06,lw=0);c.set_xlim(-6,8);c.set_xticks([-6,-3,0,3,6]);c.set_ylim(.45,3.7)
    c.set_xlabel('BF16 action − second W4 action (pp)',fontsize=9)
    M.save(fig,'f15_reference_details',['same','w3','cs'],'Supplementary W3 turnover, continuation-dependent shares and all common-state intervals; no revision-history headings or duplicate main reference panels')

if __name__=='__main__':
    patterns(); reference_details()
    p=os.path.join(M.OUT,'provenance.json');old=json.load(open(p))
    for k,v in M.PROV.items():
        v.update(script='paper/latex/tools/figs/make_supplement_details.py',script_sha256=M.script_sha());old[k]=v
    json.dump(old,open(p,'w'),indent=1,sort_keys=True)
