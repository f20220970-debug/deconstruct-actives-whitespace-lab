"""python src/plot.py -> docs/results.png (run analysis.py first)"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
S = json.loads((R / "summary.json").read_text())
dust = pd.read_csv(R / "label_dusting.csv")
reg = pd.read_csv(R / "rating_drivers.csv", index_col=0)
opp = pd.read_csv(R / "active_opportunity.csv")
fig, ax = plt.subplots(1, 4, figsize=(21, 4.8))

d = dust.sort_values("pct_below_1pct_line")
col = ["#e4572e" if n != "works below 1%: not a concern" else "#c7ccd3" for n in d.usually_needs]
ax[0].barh(d.active, d.pct_below_1pct_line, color=col)
ax[0].set_xlabel("% of products listing it AFTER phenoxyethanol (<1%)")
ax[0].set_title("1. Likely under-dosed actives (red = needs >1% to work)")

ax[1].bar(["labelled\n'for sensitive skin'", "not labelled\nfor sensitive"],
          [S["pct_sensitive_labelled_with_fragrance_or_allergens"], S["pct_not_sensitive_labelled_with_fragrance_or_allergens"]],
          color=["#e4572e", "#c7ccd3"])
ax[1].set_ylabel("% containing fragrance, allergens or essential oils"); ax[1].set_ylim(0, 100)
ax[1].set_title("2. 'Sensitive' labels vs the formula")

rr = reg.drop(index=["log_price", "n_actives"]).sort_values("coef_rating_points")
ax[2].errorbar(rr.coef_rating_points, rr.index, xerr=[rr.coef_rating_points - rr.ci_low, rr.ci_high - rr.coef_rating_points],
               fmt="o", color="#1f4e79", capsize=3)
ax[2].axvline(0, color="k", lw=.8); ax[2].set_xlabel("effect on star rating (95% CI), controls: category, price")
ax[2].set_title("3. What goes with higher ratings")

ax[3].scatter(opp.gentle_products, opp.avg_rating, s=opp.products, color="#2e7d32", alpha=.6)
for _, r in opp.iterrows():
    ax[3].annotate(r.active.split(" (")[0], (r.gentle_products, r.avg_rating), fontsize=8, xytext=(4, 2), textcoords="offset points")
ax[3].set_xscale("log"); ax[3].set_xlabel("gentle (fragrance-free, no drying alcohol) products on shelf, log")
ax[3].set_ylabel("avg rating"); ax[3].set_title("4. Whitespace: well rated, few gentle options (top-left)")
plt.tight_layout(); plt.savefig(ROOT / "docs" / "results.png", dpi=130); print("saved")
