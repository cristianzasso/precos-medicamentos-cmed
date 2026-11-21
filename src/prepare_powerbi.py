"""
Prepare the CMED/ANVISA drug price list for the Power BI dashboard.

Input : data/raw/Lista_PMC_*.xlsx   (sheet "Lista PMC", official CMED publication)
Output: data/processed/
          fact_presentation.csv      one row per presentation (GGREM code)
          fact_price_by_icms.csv     PF and PMC for every ICMS rate (long format)
          generic_vs_reference.csv   generic vs. new drug (innovator) price, same presentation

Usage : python src/prepare_powerbi.py
"""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

# São Paulo ICMS rate for medicines (used as the reference price in the dashboard)
REFERENCE_ICMS = "18 %"

PRODUCT_TYPE = {
    "Genérico": "Generic",
    "Similar": "Similar",
    "Novo": "New drug (innovator)",
    "Específico": "Specific",
    "Biológico": "Biologic",
    "Fitoterápico": "Herbal",
    "Produto de Terapia Avançada": "Advanced therapy",
    "Radiofármaco": "Radiopharmaceutical",
}

STRIPE = {
    "Tarja Vermelha": "Red stripe (prescription)",
    "Tarja Vermelha sob restrição": "Red stripe (retained prescription)",
    "Tarja Preta": "Black stripe (controlled)",
    "Tarja Sem Tarja": "No stripe (OTC)",
}

# EphMRA anatomical main groups (first letter of the therapeutic class code)
ANATOMICAL_GROUP = {
    "A": "Alimentary tract & metabolism",
    "B": "Blood & blood-forming organs",
    "C": "Cardiovascular system",
    "D": "Dermatologicals",
    "G": "Genito-urinary & sex hormones",
    "H": "Systemic hormones (excl. sex hormones)",
    "J": "Systemic anti-infectives",
    "K": "Hospital solutions",
    "L": "Antineoplastics & immunomodulators",
    "M": "Musculo-skeletal system",
    "N": "Nervous system",
    "P": "Parasitology",
    "R": "Respiratory system",
    "S": "Sensory organs",
    "T": "Diagnostic agents",
    "V": "Various",
}

DOSAGE_FORMS = [
    ("COM REV", "Coated tablet"), ("COM", "Tablet"), ("CAP", "Capsule"), ("DRG", "Tablet"),
    ("SOL INJ", "Injectable"), ("SUS INJ", "Injectable"), ("PO LIOF", "Injectable"),
    ("SOL OR", "Oral liquid"), ("SUS OR", "Oral liquid"), ("XPE", "Oral liquid"), ("GTS", "Oral liquid"),
    ("CREM", "Topical"), ("POM", "Topical"), ("GEL", "Topical"), ("LOC", "Topical"),
    ("AER", "Inhaled / nasal"), ("SPR", "Inhaled / nasal"),
]


def to_number(series: pd.Series) -> pd.Series:
    """CMED publishes prices as text with Brazilian formatting ('1.234,56')."""
    clean = series.fillna("").astype(str).str.strip()
    clean = clean.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(clean, errors="coerce")


def yes_no(series: pd.Series) -> pd.Series:
    return series.fillna("").str.strip().map({"Sim": "Yes", "Não": "No"}).fillna("Not informed")


def dosage_form(presentation: str) -> str:
    p = f" {presentation.upper()} "
    for token, label in DOSAGE_FORMS:
        if f" {token} " in p:
            return label
    return "Other"


def match_key(presentation: str) -> str:
    """Strength + dosage form + pack size, used to compare equivalent presentations."""
    p = presentation.upper()
    strength = re.match(r"^([\d,\.]+ ?[A-Z%]+(?:/[A-Z]+)?(?: \+ [\d,\.]+ ?[A-Z%]+(?:/[A-Z]+)?)*)", p)
    qty = re.search(r" X (\d+)", p)
    return " | ".join([
        strength.group(1) if strength else "?",
        dosage_form(p),
        qty.group(1) if qty else "?",
    ])


def load_raw() -> tuple[pd.DataFrame, str]:
    files = sorted(RAW_DIR.glob("Lista_PMC_*.xlsx"))
    files = [f for f in files if not f.name.startswith("~$")]
    if not files:
        sys.exit(f"No Lista_PMC_*.xlsx file found in {RAW_DIR}")
    path = files[-1]
    df = pd.read_excel(path, sheet_name="Lista PMC", dtype=str)
    df.columns = [c.replace("\xa0", " ").strip() for c in df.columns]
    pub_date = re.search(r"(\d{8})", path.name)
    return df, (pub_date.group(1) if pub_date else "")


def build_fact(df: pd.DataFrame, pub_date: str) -> pd.DataFrame:
    tipo = df["TIPO DE PRODUTO (STATUS DO PRODUTO)"].fillna("").str.strip()
    classe = df["CLASSE TERAPÊUTICA"].fillna("").str.strip()
    class_code = classe.str.split(" - ", n=1).str[0].str.strip()
    stripe = df["TARJA"].fillna("").str.strip()

    fact = pd.DataFrame({
        "ggrem_code": df["CÓDIGO GGREM"].str.strip(),
        "substance": df["SUBSTÂNCIA"].str.strip(),
        "laboratory": df["LABORATÓRIO"].str.strip(),
        "product": df["PRODUTO"].str.strip(),
        "presentation": df["APRESENTAÇÃO"].str.strip(),
        "therapeutic_class": classe,
        "therapeutic_class_code": class_code,
        "anatomical_group": class_code.str[:1].map(ANATOMICAL_GROUP).fillna("Not informed"),
        "product_type": tipo.map(PRODUCT_TYPE).fillna("Not informed"),
        "price_regime": df["REGIME DE PREÇO"].str.strip().map({"Regulado": "Regulated", "Liberado": "Free (monitored)"}),
        "stripe": stripe.map(STRIPE).fillna("Not informed"),
        "dosage_form": df["APRESENTAÇÃO"].fillna("").map(dosage_form),
        "hospital_only": yes_no(df["RESTRIÇÃO HOSPITALAR"]),
        "cap_discount": yes_no(df["CAP"]),
        "confaz_87": yes_no(df["CONFAZ 87"]),
        "icms_exempt": yes_no(df["ICMS 0%"]),
        "pis_cofins_list": df["LISTA DE CONCESSÃO DE CRÉDITO TRIBUTÁRIO (PIS/COFINS)"].str.strip()
                            .map({"Positiva": "Positive", "Negativa": "Negative", "Neutra": "Neutral"}),
        "marketed_last_year": yes_no(df["COMERCIALIZAÇÃO 2025"]),
        "pf_no_tax": to_number(df["PF Sem Impostos"]),
        "pf_sp": to_number(df[f"PF {REFERENCE_ICMS}"]),
        "pmc_no_tax": to_number(df["PMC Sem Impostos"]),
        "pmc_sp": to_number(df[f"PMC {REFERENCE_ICMS}"]),
        "match_key": df["APRESENTAÇÃO"].fillna("").map(match_key),
        "publication_date": pd.to_datetime(pub_date, format="%Y%m%d", errors="coerce").date(),
    })
    # Hospital-only presentations cannot be sold at PMC (CMED Resolution 03/2009)
    fact.loc[fact["hospital_only"] == "Yes", "pmc_sp"] = pd.NA
    return fact


def build_price_by_icms(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        m = re.match(r"^(PF|PMC) (Sem Impostos|[\d,]+ ?%)(\s+ALC)?$", col)
        if not m or m.group(3):  # skip Free Trade Zone (ALC) variants to keep the file light
            continue
        price_type, rate, _ = m.groups()
        rate_label = "No tax" if rate == "Sem Impostos" else rate.replace(" ", "")
        rate_value = None if rate == "Sem Impostos" else float(rate.replace("%", "").replace(",", ".").strip())
        rows.append(pd.DataFrame({
            "ggrem_code": df["CÓDIGO GGREM"].str.strip(),
            "price_type": price_type,
            "icms_rate": rate_label,
            "icms_rate_value": rate_value,
            "price": to_number(df[col]),
        }))
    long = pd.concat(rows, ignore_index=True)
    return long.dropna(subset=["price"])


def build_generic_vs_reference(fact: pd.DataFrame) -> pd.DataFrame:
    retail = fact[(fact["hospital_only"] == "No") & fact["pmc_sp"].notna()]
    retail = retail[~retail["match_key"].str.contains(r"\?")]
    keys = ["substance", "match_key"]
    gen = (retail[retail["product_type"] == "Generic"]
           .groupby(keys).agg(generic_pmc=("pmc_sp", "median"), generic_count=("ggrem_code", "count")))
    ref = (retail[retail["product_type"] == "New drug (innovator)"]
           .groupby(keys).agg(reference_pmc=("pmc_sp", "median"), reference_count=("ggrem_code", "count"),
                              anatomical_group=("anatomical_group", "first"),
                              therapeutic_class=("therapeutic_class", "first")))
    comp = gen.join(ref, how="inner").reset_index()
    comp["savings_pct"] = 1 - comp["generic_pmc"] / comp["reference_pmc"]
    # Flag implausible matches (different products sharing a key) instead of dropping them
    comp["valid_match"] = comp["savings_pct"].between(-0.5, 0.95).map({True: "Yes", False: "No"})
    return comp


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw, pub_date = load_raw()
    fact = build_fact(raw, pub_date)
    prices = build_price_by_icms(raw)
    comp = build_generic_vs_reference(fact)

    opts = dict(index=False, encoding="utf-8-sig", sep=";", decimal=",")
    fact.to_csv(OUT_DIR / "fact_presentation.csv", **opts)
    prices.to_csv(OUT_DIR / "fact_price_by_icms.csv", **opts)
    comp.to_csv(OUT_DIR / "generic_vs_reference.csv", **opts)

    valid = comp[comp["valid_match"] == "Yes"]
    print(f"Presentations: {len(fact):,}")
    print(f"Price rows (all ICMS rates): {len(prices):,}")
    print(f"Generic vs reference pairs: {len(comp):,} ({len(valid):,} valid)")
    print(f"Median generic savings: {valid['savings_pct'].median():.1%}")


if __name__ == "__main__":
    main()
