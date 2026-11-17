"""NPD scorecard + concept-test sizing as a live Excel model: python src/build_workbook.py -> npd_scorecard.xlsx
Blue = input (data from results/ or a judgement score), yellow = weights you can change, black = formula."""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
F, B, BL = Font(name="Arial"), Font(name="Arial", bold=True), Font(name="Arial", color="0000FF")
Y = PatternFill("solid", fgColor="FFFF00")
opp = pd.read_csv(ROOT / "results" / "active_opportunity.csv").set_index("active")
wb = Workbook(); ws = wb.active; ws.title = "NPD scorecard"
ws["A1"] = "NPD opportunity scorecard: which gentle-actives concept to brief R&D on first?"; ws["A1"].font = B
ws["A2"] = "Data columns from results/active_opportunity.csv (1,231 real Sephora formulas). Judgement columns are 1-5 scores (mine; change them). Weights in yellow."
ws["A2"].font = F
hdr = ["Concept", "Hero active", "Products with active", "Gentle products (supply)", "Avg rating", "Median price (USD)",
       "Brand fit (1-5)", "R&D ease (1-5)", "Scarcity score", "Rating score", "Score"]
ws.append([]); ws.append(hdr)
for c in ws[4]:
    c.font = B; c.alignment = Alignment(wrap_text=True)
concepts = [("Fragrance-free ceramide barrier moisturiser", "ceramides", 5, 4),
            ("Gentle mineral (zinc oxide) sunscreen", "zinc oxide (mineral filter)", 5, 2),
            ("Centella calming serum", "centella", 4, 4),
            ("Properly dosed glycolic serum, fragrance-free", "glycolic acid (AHA)", 4, 3),
            ("Niacinamide 5% serum, fragrance-free", "niacinamide", 3, 5),
            ("Gentle retinoid serum", "retinoids", 4, 2)]
first = 5
for i, (name, act, fit, ease) in enumerate(concepts, first):
    r = opp.loc[act]
    ws.cell(i, 1, name); ws.cell(i, 2, act)
    for j, v in enumerate([int(r.products), int(r.gentle_products), float(r.avg_rating), float(r.median_price_usd), fit, ease], 3):
        ws.cell(i, j, v).font = BL
last = first + len(concepts) - 1
for i in range(first, last + 1):
    # scarcity: fewer gentle options = higher (1 = most crowded, 5 = scarcest); rating: scaled 1-5 across concepts
    ws.cell(i, 9, f"=1+4*(MAX($D${first}:$D${last})-D{i})/(MAX($D${first}:$D${last})-MIN($D${first}:$D${last}))").number_format = "0.0"
    ws.cell(i, 10, f"=1+4*(E{i}-MIN($E${first}:$E${last}))/(MAX($E${first}:$E${last})-MIN($E${first}:$E${last}))").number_format = "0.0"
    ws.cell(i, 11, f"=($B${last+3}*G{i}+$B${last+4}*H{i}+$B${last+5}*I{i}+$B${last+6}*J{i})/SUM($B${last+3}:$B${last+6})").number_format = "0.00"
    ws.cell(i, 12, f"=RANK(K{i},$K${first}:$K${last})")
ws.cell(4, 12, "Rank").font = B
ws.cell(last + 2, 1, "Weights").font = B
for k, (lab, w) in enumerate([("Brand fit", 0.3), ("R&D ease", 0.2), ("Scarcity of gentle options", 0.3), ("Shopper rating", 0.2)], last + 3):
    ws.cell(k, 1, lab); c = ws.cell(k, 2, w); c.font = BL; c.fill = Y
ws.cell(last + 8, 1, "Scarcity is supply in a US prestige retailer; validate in India (Nykaa, Amazon, quick commerce) before briefing.").font = F
for col, w in zip("ABCDEFGHIJKL", [44, 26, 12, 14, 10, 12, 10, 10, 11, 11, 9, 7]):
    ws.column_dimensions[col].width = w

# Concept test sizing
cs = wb.create_sheet("Concept test size")
rows = [("Top-2-box purchase intent, control concept", 0.30, "0%"), ("Smallest lift worth detecting (pts)", 0.08, "0%"),
        ("Significance (two-sided)", 0.05, "0%"), ("Power", 0.80, "0%")]
cs["A1"] = "How many respondents per concept for a monadic concept test?"; cs["A1"].font = B
for i, (lab, v, fmt) in enumerate(rows, 3):
    cs.cell(i, 1, lab); c = cs.cell(i, 2, v); c.font = BL; c.fill = Y; c.number_format = fmt
cs["A8"] = "Respondents per concept"
cs["B8"] = "=ROUNDUP((NORMSINV(1-B5/2)+NORMSINV(B6))^2*(B3*(1-B3)+(B3+B4)*(1-B3-B4))/B4^2,0)"
cs["A9"] = "Total for 3 concepts + control"; cs["B9"] = "=B8*4"
cs["A11"] = "Two-proportion z-test approximation. A lift of 8 pts on 30% needs about 550 per arm; halving the lift roughly quadruples it."
cs.column_dimensions["A"].width = 48; cs.column_dimensions["B"].width = 12
for wsx in wb.worksheets:
    for row in wsx.iter_rows():
        for c in row:
            if c.font != BL and not c.font.bold:
                c.font = F
wb.save(ROOT / "npd_scorecard.xlsx"); print("saved")
