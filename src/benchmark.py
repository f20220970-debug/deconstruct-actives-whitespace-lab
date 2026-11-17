"""Formula benchmarking tool for NPD: paste a draft ingredient list, get the closest products on the market.

Each product becomes a vector of its ingredients, weighted by position (ingredients near the top of an INCI
list are present at higher concentration, so weight = 1/sqrt(position)) and by rarity (IDF: water and
glycerin are everywhere and say little). Similarity = cosine.

Evaluation first: before trusting it, check that a formula's nearest neighbours are the same kind of
product. Leave-one-out: predict each product's category from its 5 nearest formulas, vs a majority baseline.

Run: python src/benchmark.py -> results/benchmark_eval.json, results/benchmark_concept.csv
"""
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from inci import clean_list

ROOT = Path(__file__).resolve().parents[1]

# A draft concept a brand team might bring to R&D: a fragrance-free barrier moisturiser
# (illustrative formula written for this project, not a real product).
CONCEPT = ("Water, Glycerin, Caprylic/Capric Triglyceride, Niacinamide, Cetearyl Alcohol, Squalane, Butylene Glycol, "
           "Ceramide NP, Ceramide AP, Ceramide EOP, Phytosphingosine, Cholesterol, Sodium Hyaluronate, Panthenol, "
           "Allantoin, Glyceryl Stearate, Ceteareth-20, Carbomer, Xanthan Gum, Sodium Lauroyl Lactylate, "
           "Phenoxyethanol, Ethylhexylglycerin")


def norm_ing(x):
    """'Ceramide NP', 'Ceramide 3' and 'Ceramide AP' all become 'ceramide' (tested: best of 3 variants)."""
    x = x.replace(";", ",").strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"\b(np|ap|eop|ns|eos|[0-9]+)\b", "", x)).strip()


class Benchmarker:
    def __init__(self, df):
        self.df = df.reset_index(drop=True)
        lists = [[norm_ing(i) for i in clean_list(r)] for r in self.df.Ingredients]
        vocab = Counter(i for l in lists for i in set(l))
        self.vocab = {t: k for k, t in enumerate(t for t, c in vocab.items() if c >= 2)}
        n = len(lists)
        self.idf = np.zeros(len(self.vocab))
        for t, k in self.vocab.items():
            self.idf[k] = np.log((1 + n) / (1 + vocab[t])) + 1
        self.X = self._vectorise(lists)

    def _vectorise(self, lists):
        rows, cols, vals = [], [], []
        for r, l in enumerate(lists):
            seen = set()
            for pos, ing in enumerate(l, 1):
                k = self.vocab.get(ing)
                if k is None or k in seen:
                    continue
                seen.add(k)
                rows.append(r); cols.append(k); vals.append(self.idf[k] / np.sqrt(pos))
        X = csr_matrix((vals, (rows, cols)), shape=(len(lists), len(self.vocab)))
        norms = np.sqrt(X.multiply(X).sum(axis=1)).A.ravel()
        norms[norms == 0] = 1
        return csr_matrix(X.multiply(1 / norms[:, None]))

    def query(self, inci_text, k=8, category=None, gentle_only=False):
        """Closest products; filter to the target category first (formulas alone separate categories poorly)."""
        v = self._vectorise([[norm_ing(i) for i in clean_list(inci_text)]])
        sim = (self.X @ v.T).toarray().ravel()
        ok = np.ones(len(sim), bool)
        if category:
            ok &= (self.df.category == category).values
        if gentle_only:
            ok &= self.df.gentle.values.astype(bool)
        sim = np.where(ok, sim, -1)
        top = np.argsort(-sim)[:k]
        out = self.df.iloc[top][["category", "Brand", "Name", "price_usd", "rating"]].copy()
        out["similarity"] = sim[top].round(3)
        return out

    def loo_category_accuracy(self, k=5):
        S = (self.X @ self.X.T).toarray()
        np.fill_diagonal(S, -1)
        cats = self.df.category.values
        pred = []
        for i in range(len(cats)):
            nb = np.argsort(-S[i])[:k]
            pred.append(Counter(cats[nb]).most_common(1)[0][0])
        acc = float(np.mean(np.array(pred) == cats))
        base = float(pd.Series(cats).value_counts(normalize=True).iloc[0])
        return acc, base


def main():
    from analysis import load
    d = load()
    d = d[(d.usable == True) & (d.rating > 0)]  # noqa: E712
    b = Benchmarker(d)
    acc, base = b.loo_category_accuracy()
    res = b.query(CONCEPT, category="Moisturizer")
    res.to_csv(ROOT / "results" / "benchmark_concept.csv", index=False)
    gentle = b.query(CONCEPT, category="Moisturizer", gentle_only=True)
    gentle.to_csv(ROOT / "results" / "benchmark_concept_gentle.csv", index=False)
    out = {"products_indexed": len(d), "vocabulary": len(b.vocab), "loo_5nn_category_accuracy": round(100 * acc, 1),
           "majority_baseline": round(100 * base, 1),
           "concept_top8_median_price_usd": float(res.price_usd.median()), "concept_top8_avg_rating": round(float(res.rating.mean()), 2),
           "gentle_competitors_top8_median_price_usd": float(gentle.price_usd.median()),
           "gentle_competitors_top8_avg_rating": round(float(gentle.rating.mean()), 2)}
    (ROOT / "results" / "benchmark_eval.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)); print(res.to_string(index=False)); print(gentle.to_string(index=False))


if __name__ == "__main__":
    main()
