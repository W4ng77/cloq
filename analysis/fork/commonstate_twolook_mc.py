"""W100u (COMMONSTATE_SOURCES_PROTOCOL.md amendment A1.3): error rates of the two looks at the common-state reading
(k = 3 blocks, then k = 6 with the first three blocks shared). A design property: no data is read.

Model: block-level K estimates iid N(mu, sd^2) in pp; the t criterion over block means (df = k - 1) of the frozen rule.
The frozen rule also needs the bootstrap interval, so its claim rates are at most these.
  difference claim: |mean| > t_{1-a/2, k-1} * se            (a = 0.05 frozen; a = 0.0294 Pocock, two-sided)
  equivalence:      mean -/+ t_{1-a, k-1} * se inside (-3, 3) (a = 0.05 frozen; a = 0.0304 Pocock, one-sided per side)
Pocock constants for two equally spaced looks are computed from the bivariate normal with correlation sqrt(1/2).

usage: python analysis/fork/commonstate_twolook_mc.py   (needs scipy; ~20 s)
       python analysis/fork/commonstate_twolook_mc.py --given   (deviation D2: rates conditional on the observed first look,
           i.e. f01-f03 block values fixed at their W100b values and only f04-f06 drawn; default output unchanged)
"""
import sys
import numpy as np
from scipy import optimize, stats

RHO = np.sqrt(0.5)
MVN = stats.multivariate_normal(mean=[0, 0], cov=[[1, RHO], [RHO, 1]])


def pocock() -> tuple[float, float]:
    inside = lambda c: MVN.cdf([c, c]) - MVN.cdf([-c, c]) - MVN.cdf([c, -c]) + MVN.cdf([-c, -c])  # noqa: E731
    c2 = optimize.brentq(lambda c: 1 - inside(c) - 0.05, 1.9, 2.6)  # two-sided
    c1 = optimize.brentq(lambda c: 1 - MVN.cdf([c, c]) - 0.05, 1.5, 2.3)  # one-sided
    return 2 * stats.norm.sf(c2), stats.norm.sf(c1)


def sim(mu: float, sd: float, a_diff: float, a_eq: float, n: int, rng) -> dict:
    x = rng.normal(mu, sd, size=(n, 6))
    out = {}
    for k in (3, 6):
        m, se = x[:, :k].mean(1), x[:, :k].std(1, ddof=1) / np.sqrt(k)
        out[f"diff{k}"] = np.abs(m) > stats.t.ppf(1 - a_diff / 2, k - 1) * se
        tt = stats.t.ppf(1 - a_eq, k - 1)
        out[f"eq{k}"] = (m - tt * se > -3) & (m + tt * se < 3)
    return out


GIVEN = {"K[bf16]": (0.0, 2.35, 4.71), "K[d1]": (-3.53, -1.18, 3.53)}  # W100b block means (pp), commonstate_20261002T201612Z.json


def given(a2: float, a1: float) -> None:
    """D2: P(claim at k = 6) with the first three blocks fixed at the observed values; f04-f06 iid N(mu, sd^2)."""
    rng, n = np.random.default_rng(20261003), 400_000
    for key, v in GIVEN.items():
        for mu in (0.0, 3.0, -3.0):
            for sd in (2.0, 2.35, 3.5, 6.0):
                x = np.hstack([np.tile(v, (n, 1)), rng.normal(mu, sd, size=(n, 3))])
                m, se = x.mean(1), x.std(1, ddof=1) / np.sqrt(6)
                r = {}
                for lab, ad, ae in (("frozen", 0.05, 0.05), ("pocock", a2, a1)):
                    r[lab] = ((np.abs(m) > stats.t.ppf(1 - ad / 2, 5) * se).mean(),
                              ((m - stats.t.ppf(1 - ae, 5) * se > -3) & (m + stats.t.ppf(1 - ae, 5) * se < 3)).mean())
                print(f"{key} first look {v}, f04-f06 ~ N({mu:+.0f}, {sd}): P(diff k6) frozen {r['frozen'][0]:.4f} pocock {r['pocock'][0]:.4f}; "
                      f"P(eq k6) frozen {r['frozen'][1]:.4f} pocock {r['pocock'][1]:.4f}")


def main():
    a2, a1 = pocock()
    if "--given" in sys.argv[1:]:
        return given(a2, a1)
    print(f"Pocock, 2 looks: nominal two-sided {a2:.4f} (two-sided alpha 0.05), nominal one-sided {a1:.4f} (one-sided 0.05)")
    for df in range(1, 6):
        print(f"  df={df}: t at two-sided {a2:.4f} = {stats.t.ppf(1 - a2 / 2, df):.3f}; t at one-sided {a1:.4f} = {stats.t.ppf(1 - a1, df):.3f}")
    rng, n = np.random.default_rng(20261003), 400_000
    for sd in (2.0, 3.6, 6.0):
        o, p = sim(0.0, sd, 0.05, 0.05, n, rng), sim(0.0, sd, a2, a1, n, rng)
        print(f"sd {sd} pp, K = 0: P(diff k6 | none k3) {o['diff6'][~o['diff3']].mean():.4f}; two-look frozen {(o['diff3'] | o['diff6']).mean():.4f}; "
              f"two-look Pocock {(p['diff3'] | p['diff6']).mean():.4f}")
        o, p = sim(3.0, sd, 0.05, 0.05, n, rng), sim(3.0, sd, a2, a1, n, rng)
        print(f"sd {sd} pp, K = 3 pp: P(eq k6 | none k3) {o['eq6'][~o['eq3']].mean():.4f}; two-look frozen {(o['eq3'] | o['eq6']).mean():.4f}; "
              f"two-look Pocock {(p['eq3'] | p['eq6']).mean():.4f}")


if __name__ == "__main__":
    main()
