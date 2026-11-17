"""Actives & whitespace lab: what a science-first skincare brand can learn from 1,472 real product formulas.

Data (real, public): 1,472 Sephora skincare products with full ingredient lists, price, rating and skin-type
labels, plus 10,820 Sephora listings with review counts (merged by product name where possible).
US data, so a proxy for India: the method transfers; prices and ratings will differ.

Run: python src/analysis.py -> results/*.csv, results/summary.json
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from inci import ACTIVES, NEEDS_ABOVE_1PCT, profile_frame

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(exist_ok=True)


def load():
    d = pd.read_csv(ROOT / "data" / "sephora_skincare_ingredients.csv")
    d = d.join(profile_frame(d))
    r = pd.read_csv(ROOT / "data" / "sephora_ratings_reviews.tsv", sep="\t", lineterminator="\r")
    norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    r["key"] = [norm(n.replace(b, "", 1)) if isinstance(n, str) and isinstance(b, str) else norm(n)
                for n, b in zip(r["Product Name"], r["Brand Name"])]
    d["key"] = d.Name.map(norm)
    d = d.merge(r[["key", "Number of Reviews"]].drop_duplicates("key"), on="key", how="left")
    return d.rename(columns={"Label": "category", "Rank": "rating", "Price": "price_usd", "Number of Reviews": "reviews"})


def main():
    d = load()
    u = d[(d.usable == True) & (d.rating > 0)].copy()  # noqa: E712
    flags = [c for c in u.columns if c.split("::")[0] in ("has", "above1pct", "below1pct")] + \
        ["fragrance", "allergens", "essential_oils", "drying_alcohol", "any_fragrance_source", "gentle"]
    u[flags] = u[flags].astype(bool)
    S = {"products": int(len(d)), "usable_ingredient_lists": int(len(u)), "with_review_counts": int(u.reviews.notna().sum()),
         "pct_with_phenoxyethanol": round(100 * float(u.one_pct_line_pos.notna().mean()), 1)}

    # 1. Label dusting: of products containing an active, how often is it below the 1% line?
    rows = []
    has1 = u[u.one_pct_line_pos.notna()]
    for a in ACTIVES:
        if a in ("zinc oxide (mineral filter)", "chemical UV filters"):
            continue
        n = int(has1[f"has::{a}"].sum())
        if n < 15:
            continue
        rows.append({"active": a, "products_with_it": n,
                     "pct_above_1pct_line": round(100 * has1[f"above1pct::{a}"].sum() / n, 1),
                     "pct_below_1pct_line": round(100 * has1[f"below1pct::{a}"].sum() / n, 1),
                     "median_price_usd": float(has1.loc[has1[f"has::{a}"], "price_usd"].median())})
    dust = pd.DataFrame(rows).sort_values("pct_below_1pct_line", ascending=False)
    dust.to_csv(RES / "label_dusting.csv", index=False)
    dust["usually_needs"] = dust.active.map(NEEDS_ABOVE_1PCT).fillna("works below 1%: not a concern")
    dust.to_csv(RES / "label_dusting.csv", index=False)
    need = [a for a in dust.active if a in NEEDS_ABOVE_1PCT]
    S["likely_underdosed_pct"] = round(100 * sum(has1[f"below1pct::{a}"].sum() for a in need) / sum(has1[f"has::{a}"].sum() for a in need), 1)
    S["likely_underdosed_products"] = int(sum(has1[f"below1pct::{a}"].sum() for a in need))
    S["actives_needing_1pct_checked"] = need
    # price of underdosed vs properly dosed products, same actives
    rows2 = []
    for a in need:
        k = has1[has1[f"has::{a}"]]
        rows2.append({"active": a, "median_price_dosed": k[k[f"above1pct::{a}"]].price_usd.median(),
                      "median_price_underdosed": k[k[f"below1pct::{a}"]].price_usd.median(),
                      "rating_dosed": round(k[k[f"above1pct::{a}"]].rating.mean(), 2),
                      "rating_underdosed": round(k[k[f"below1pct::{a}"]].rating.mean(), 2)})
    pd.DataFrame(rows2).to_csv(RES / "dosed_vs_underdosed.csv", index=False)

    # 2. "For sensitive skin" vs what's in the bottle
    sens = u[u.Sensitive == 1]; non = u[u.Sensitive == 0]
    S["sensitive_labelled_products"] = int(len(sens))
    S["pct_sensitive_labelled_with_fragrance_or_allergens"] = round(100 * float(sens.any_fragrance_source.mean()), 1)
    S["pct_not_sensitive_labelled_with_fragrance_or_allergens"] = round(100 * float(non.any_fragrance_source.mean()), 1)
    S["pct_sensitive_labelled_with_drying_alcohol"] = round(100 * float(sens.drying_alcohol.mean()), 1)
    S["pct_all_products_gentle"] = round(100 * float(u.gentle.mean()), 1)

    # 3. Whitespace: category x active, supply of GENTLE versions vs how well they're rated
    rows = []
    for cat, g in u.groupby("category"):
        for a in ACTIVES:
            k = g[g[f"has::{a}"]]
            if len(k) < 8:
                continue
            gen = k[k.gentle]
            rows.append({"category": cat, "active": a, "products": len(k), "gentle_products": len(gen),
                         "pct_gentle": round(100 * len(gen) / len(k), 1),
                         "avg_rating": round(k.rating.mean(), 2),
                         "avg_rating_gentle": round(gen.rating.mean(), 2) if len(gen) >= 3 else np.nan,
                         "avg_rating_not_gentle": round(k[~k.gentle].rating.mean(), 2) if (~k.gentle).sum() >= 3 else np.nan,
                         "median_price_usd": float(k.price_usd.median()),
                         "median_reviews": float(k.reviews.median()) if k.reviews.notna().any() else np.nan})
    ws = pd.DataFrame(rows)
    ws = ws.sort_values(["category", "products"], ascending=[True, False])
    ws.to_csv(RES / "whitespace_matrix.csv", index=False)

    # 4. Do gentle formulas rate worse? (does "gentle" cost anything with shoppers?)
    S["avg_rating_gentle"] = round(float(u[u.gentle].rating.mean()), 3)
    S["avg_rating_not_gentle"] = round(float(u[~u.gentle].rating.mean()), 3)
    X = pd.get_dummies(u[["category"]], drop_first=True, dtype=float)
    X["log_price"] = np.log(u.price_usd.clip(lower=1))
    X["gentle"] = u.gentle.astype(float)
    X["n_actives"] = u.n_actives
    for a in ["niacinamide", "retinoids", "vitamin C", "salicylic acid (BHA)", "hyaluronic acid", "ceramides", "peptides"]:
        X[a] = u[f"has::{a}"].astype(float)
    lr = LinearRegression().fit(X, u.rating)
    coefs = pd.Series(lr.coef_, index=X.columns)
    rng = np.random.default_rng(0); boot = []
    for _ in range(500):
        ix = rng.integers(0, len(u), len(u))
        boot.append(LinearRegression().fit(X.iloc[ix], u.rating.iloc[ix]).coef_)
    boot = np.array(boot)
    reg = pd.DataFrame({"coef_rating_points": coefs.round(3),
                        "ci_low": np.percentile(boot, 2.5, axis=0).round(3), "ci_high": np.percentile(boot, 97.5, axis=0).round(3)})
    reg = reg.loc[[c for c in reg.index if not c.startswith("category_")]]
    reg.to_csv(RES / "rating_drivers.csv")
    S["price_doubling_effect_on_rating"] = round(float(coefs["log_price"] * np.log(2)), 3)

    # 5. Price: what do actives and 'gentle' cost at Sephora? (median price by category, gentle vs not)
    pr = u.groupby(["category", "gentle"]).price_usd.median().unstack().rename(columns={True: "gentle", False: "not_gentle"})
    pr["products"] = u.groupby("category").size()
    pr.round(1).to_csv(RES / "price_gentle_by_category.csv")

    # Opportunity by active: shopper rating signal (regression) x how few GENTLE, properly-dosed options exist
    opp = []
    for a in ACTIVES:
        k = u[u[f"has::{a}"]]
        if len(k) < 20:
            continue
        g = k[k.gentle]
        opp.append({"active": a, "products": len(k), "gentle_products": len(g), "pct_gentle": round(100 * len(g) / len(k), 1),
                    "avg_rating": round(k.rating.mean(), 2), "rating_coef": float(coefs.get(a, np.nan)),
                    "median_price_usd": float(k.price_usd.median())})
    opp = pd.DataFrame(opp).sort_values("gentle_products")
    opp.to_csv(RES / "active_opportunity.csv", index=False)
    S["top_whitespace"] = opp.to_dict(orient="records")
    S["label_dusting"] = dust.to_dict(orient="records")
    S["rating_drivers"] = reg.reset_index().rename(columns={"index": "feature"}).to_dict(orient="records")
    (RES / "summary.json").write_text(json.dumps(S, indent=1, default=float))
    pd.set_option("display.width", 220)
    print(json.dumps({k: v for k, v in S.items() if not isinstance(v, list)}, indent=1))
    print(dust.to_string(index=False)); print(ws.head(15).to_string(index=False)); print(reg.to_string()); print(pr.round(1).to_string())
    return u


if __name__ == "__main__":
    main()
