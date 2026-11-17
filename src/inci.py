"""Ingredient (INCI) list parsing: a chemist's rules, written so a brand or R&D team can audit them.

Key idea: INCI lists ingredients in descending order of concentration down to 1%, after which the order is
free. Phenoxyethanol, the most common preservative, is capped at 1% (EU Annex V; commonly 0.5-1%). So an
active listed BEFORE phenoxyethanol is very likely present at >= 1%, and one listed after it is below 1%:
there for the label, not for the skin ("label dusting").
"""
import re

import pandas as pd

ACTIVES = {
    "niacinamide": [r"\bniacinamide\b"],
    "salicylic acid (BHA)": [r"\bsalicylic acid\b", r"\bwillow bark\b"],
    "glycolic acid (AHA)": [r"\bglycolic acid\b"],
    "lactic acid (AHA)": [r"\blactic acid\b"],
    "mandelic acid": [r"\bmandelic acid\b"],
    "retinoids": [r"\bretinol\b", r"\bretinal\b", r"\bretinyl\b", r"\bhydroxypinacolone retinoate\b"],
    "bakuchiol": [r"\bbakuchiol\b"],
    "vitamin C": [r"\bascorbic acid\b", r"\bascorbyl\b", r"\btetrahexyldecyl ascorbate\b", r"\bascorbyl glucoside\b"],
    "hyaluronic acid": [r"\bhyaluronic acid\b", r"\bsodium hyaluronate\b", r"\bhyaluronate\b"],
    "ceramides": [r"\bceramide\b"],
    "peptides": [r"\bpeptide\b", r"\bpalmitoyl\b", r"\bacetyl hexapeptide\b", r"\bmatrixyl\b"],
    "azelaic acid": [r"\bazelaic acid\b", r"\bazeloyl\b"],
    "alpha arbutin": [r"\barbutin\b"],
    "tranexamic acid": [r"\btranexamic acid\b"],
    "centella": [r"\bcentella asiatica\b", r"\bmadecassoside\b", r"\basiaticoside\b"],
    "zinc oxide (mineral filter)": [r"\bzinc oxide\b"],
    "chemical UV filters": [r"\bavobenzone\b", r"\boctinoxate\b", r"\boxybenzone\b", r"\boctisalate\b", r"\bhomosalate\b",
                            r"\boctocrylene\b", r"\bethylhexyl methoxycinnamate\b"],
}
# Approximate lower end of the concentration at which each active is usually studied/used for its main
# benefit (dermatology and cosmetic-science literature; e.g. niacinamide 2-5%, L-ascorbic acid 8-20%,
# glycolic/lactic acid ~5-10%, azelaic acid 10-20%, tranexamic acid 2-5%). Actives that work BELOW 1%
# (retinol 0.1-1%, hyaluronic acid 0.1-2%, peptides at ppm, ceramides, salicylic acid 0.5-2%) are excluded,
# because being after phenoxyethanol says nothing bad about them.
NEEDS_ABOVE_1PCT = {"niacinamide": "2-5%", "vitamin C": "8-20% (L-ascorbic acid)", "glycolic acid (AHA)": "5-10%",
                    "lactic acid (AHA)": "5-12%", "mandelic acid": "5-10%", "azelaic acid": "10-20%",
                    "tranexamic acid": "2-5%"}
FRAGRANCE = [r"\bfragrance\b", r"\bparfum\b", r"\baroma\b"]
ALLERGENS = [r"\blimonene\b", r"\blinalool\b", r"\bcitral\b", r"\bgeraniol\b", r"\beugenol\b", r"\bcitronellol\b",
             r"\bcoumarin\b", r"\bbenzyl (alcohol|benzoate|salicylate)\b", r"\bhexyl cinnamal\b", r"\bfarnesol\b"]
ESSENTIAL_OILS = [r"\b(lavender|lavandula|peppermint|mentha|eucalyptus|citrus|bergamot|lemon|orange|rosemary|tea tree|"
                  r"melaleuca|ylang|geranium|rose flower) .{0,40}\boil\b"]
DRYING_ALCOHOL = [r"\balcohol denat\b", r"\bsd alcohol\b", r"\bdenatured alcohol\b", r"\bethanol\b"]
ONE_PCT_MARKER = re.compile(r"\bphenoxyethanol\b")


def clean_list(raw: str):
    """Return a list of ingredient names, or None if the text is not a usable INCI list."""
    if not isinstance(raw, str) or "no info" in raw.lower() or "visit the" in raw.lower():
        return None
    s = raw
    if s.lstrip().startswith("-"):                      # marketing bullets first ("-Vitamin K3: ..."), INCI after
        m = re.search(r"\b(Water|Aqua)\b", s)
        if not m:
            return None
        s = s[m.start():]
    s = re.sub(r"\([^)]*\)", lambda m: m.group(0).replace(",", ";"), s)   # keep commas inside brackets
    items = [re.sub(r"[*.\s]+$", "", x.strip().lower()) for x in s.split(",")]
    items = [x for x in items if 1 < len(x) < 120]
    return items if len(items) >= 4 else None


def first_pos(items, patterns):
    rx = re.compile("|".join(patterns))
    for i, x in enumerate(items, 1):
        if rx.search(x):
            return i
    return None


def profile(items):
    """Per-product flags: actives (with position and whether above the 1% line), fragrance, allergens, alcohol."""
    out = {"n_ingredients": len(items)}
    marker = next((i for i, x in enumerate(items, 1) if ONE_PCT_MARKER.search(x)), None)
    out["one_pct_line_pos"] = marker
    for name, pats in ACTIVES.items():
        p = first_pos(items, pats)
        out[f"has::{name}"] = p is not None
        out[f"pos::{name}"] = p
        out[f"above1pct::{name}"] = (p is not None and marker is not None and p < marker)
        out[f"below1pct::{name}"] = (p is not None and marker is not None and p > marker)
    out["fragrance"] = first_pos(items, FRAGRANCE) is not None
    out["allergens"] = first_pos(items, ALLERGENS) is not None
    out["essential_oils"] = first_pos(items, ESSENTIAL_OILS) is not None
    out["drying_alcohol"] = first_pos(items, DRYING_ALCOHOL) is not None
    out["any_fragrance_source"] = out["fragrance"] or out["allergens"] or out["essential_oils"]
    out["gentle"] = not (out["any_fragrance_source"] or out["drying_alcohol"])
    out["n_actives"] = sum(out[f"has::{a}"] for a in ACTIVES)
    return out


def profile_frame(df: pd.DataFrame, col="Ingredients") -> pd.DataFrame:
    rows = []
    for raw in df[col]:
        items = clean_list(raw)
        rows.append({"usable": False} if items is None else {"usable": True, **profile(items)})
    return pd.DataFrame(rows, index=df.index)
