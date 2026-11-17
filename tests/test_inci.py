from inci import clean_list, profile


def p(s):
    return profile(clean_list(s))


def test_one_percent_line():
    x = p("Water, Glycerin, Niacinamide, Butylene Glycol, Phenoxyethanol, Glycolic Acid, Fragrance")
    assert x["above1pct::niacinamide"] and not x["below1pct::niacinamide"]
    assert x["below1pct::glycolic acid (AHA)"]          # after phenoxyethanol -> under 1%


def test_fragrance_and_gentle():
    assert not p("Water, Glycerin, Squalane, Linalool, Phenoxyethanol")["gentle"]    # allergen
    assert not p("Water, Alcohol Denat., Glycerin, Panthenol")["gentle"]             # drying alcohol
    assert p("Water, Glycerin, Ceramide NP, Cholesterol, Phenoxyethanol")["gentle"]


def test_commas_inside_brackets_and_marketing_text():
    items = clean_list("-Aloe: soothes. -Vitamin E: protects. Water, Titanium Dioxide (CI 77891, Nano), Glycerin, Panthenol")
    assert items[0] == "water" and any("titanium dioxide" in i for i in items)
    assert clean_list("Visit the Dior boutique for complete list") is None


def test_benchmark_finds_itself():
    import pandas as pd
    from benchmark import Benchmarker
    df = pd.DataFrame({"Ingredients": ["Water, Glycerin, Niacinamide, Zinc PCA, Phenoxyethanol",
                                       "Water, Glycerin, Ceramide NP, Cholesterol, Phenoxyethanol",
                                       "Water, Glycerin, Ceramide AP, Cholesterol, Squalane, Phenoxyethanol"],
                       "category": ["Treatment", "Moisturizer", "Moisturizer"], "Brand": list("abc"), "Name": list("xyz"),
                       "price_usd": [10, 20, 30], "rating": [4, 4, 4], "gentle": [True] * 3})
    top = Benchmarker(df).query("Water, Glycerin, Ceramide EOP, Cholesterol, Phenoxyethanol", k=2)
    assert set(top.Name) == {"y", "z"}                   # ceramide variants are matched as one ingredient
