import json
from datetime import datetime
from pathlib import Path

YEAR = 2025
OUT_PATH = Path("data/top10_2025.json")

# Donor kulcs = ami a weben megjelenik
DONORS = {
    "EU": "European Union",
    "USA": "United States",
    "Germany": "Germany",
    "UK": "United Kingdom",
    "Japan": "Japan",
    "France": "France",
    "Canada": "Canada",
    "Sweden": "Sweden",
    "Norway": "Norway",
    "Netherlands": "Netherlands",
}

# 2 féle támogatás (külön értékekkel)
TYPES = {
    "commitments": "commit",      # jelölő a későbbi szűréshez
    "disbursements": "disburse",  # jelölő a későbbi szűréshez
}

def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

def _pick_value_col(df):
    """Megpróbálja kitalálni az érték oszlopot (oda_data különböző verzióknál eltérhet)."""
    for c in ["value", "Value", "OBS_VALUE", "obs_value", "amount", "Amount"]:
        if c in df.columns:
            return c
    return None

def _find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _normalize_text(x):
    return (str(x) if x is not None else "").strip().lower()

def _is_commitment(row, measure_col):
    m = _normalize_text(row.get(measure_col))
    # tipikus megnevezések: "Commitments", "Total commitments", stb.
    return "commit" in m

def _is_disbursement(row, measure_col):
    m = _normalize_text(row.get(measure_col))
    # tipikus megnevezések: "Disbursements", "Gross disbursements", stb.
    return "disburs" in m

def fetch_top10_for_donor(donor_name: str):
    """
    OECD ODA adatok lekérése oda_data csomagon keresztül.
    Cél: donor -> TOP10 recipiens lista (commitments és disbursements külön).
    """
    try:
        # oda_data telepítve lesz a workflowban
        from oda_data import oda_reader
    except Exception as e:
        print("ERROR: oda_data nincs telepítve:", e)
        return {k: [] for k in TYPES.keys()}

    # Megpróbáljuk a DAC1 táblát letölteni donor+év szűréssel.
    # A paraméterek az oda_data verziótól függhetnek, ezért több fallback-et is adunk.
    df = None
    errors = []

    # 1) Legszűkebb próbálkozás
    try:
        df = oda_reader.download_dac1(donor=donor_name, year=YEAR, dotstat_codes=False)
    except Exception as e:
        errors.append(f"download_dac1(donor, year) failed: {e}")

    # 2) Fallback: csak donor, majd szűrünk
    if df is None:
        try:
            df = oda_reader.download_dac1(donor=donor_name, dotstat_codes=False)
            # year szűrés később
        except Exception as e:
            errors.append(f"download_dac1(donor) failed: {e}")

    if df is None:
        print("ERROR: Nem sikerült adatot letölteni a donorhoz:", donor_name)
        for msg in errors:
            print("  -", msg)
        return {k: [] for k in TYPES.keys()}

    # Oszlopok kitalálása
    value_col = _pick_value_col(df)
    year_col = _find_col(df, ["year", "Year", "TIME_PERIOD", "time_period"])
    recip_col = _find_col(df, ["recipient", "Recipient", "RECIPIENT", "recipient_name"])
    measure_col = _find_col(df, ["measure", "Measure", "MEASURE", "measure_name"])
    flow_col = _find_col(df, ["flow_type", "Flow type", "FLOW_TYPE", "flow"])

    if value_col is None or year_col is None or recip_col is None:
        print("ERROR: Hiányzó szükséges oszlop(ok). Oszlopok:", list(df.columns))
        return {k: [] for k in TYPES.keys()}

    # Év szűrés
    try:
        df = df[df[year_col].astype(str) == str(YEAR)]
    except Exception:
        # ha valamiért nem sztringesíthető
        df = df[df[year_col] == YEAR]

    # ODA szűrés (ha van flow oszlop)
    # Nem erőltetjük túl: ha felismerhető "oda", akkor szűrjük.
    if flow_col is not None:
        flow_txt = df[flow_col].astype(str).str.lower()
        # tipikus: "ODA", "Total ODA", stb.
        df = df[flow_txt.str.contains("oda", na=False)]

    # Érték oszlop float
    df = df.copy()
    df[value_col] = df[value_col].apply(_safe_float)

    # kiszórjuk a hiányzókat
    df = df[df[value_col].notna()]

    # commitments / disbursements top10 számítás
    out = {k: [] for k in TYPES.keys()}

    if measure_col is None:
        # ha nincs measure, akkor legalább egy listát adunk vissza "disbursements" néven
        grp = df.groupby(recip_col, as_index=False)[value_col].sum()
        grp = grp.sort_values(value_col, ascending=False).head(10)
        out["disbursements"] = [
            {"country": str(r[recip_col]), "amount": float(r[value_col])}
            for _, r in grp.iterrows()
        ]
        out["commitments"] = []
        return out

    # commitments
    df_commit = df[df.apply(lambda r: _is_commitment(r, measure_col), axis=1)]
    grp_c = df_commit.groupby(recip_col, as_index=False)[value_col].sum()
    grp_c = grp_c.sort_values(value_col, ascending=False).head(10)
    out["commitments"] = [
        {"country": str(r[recip_col]), "amount": float(r[value_col])}
        for _, r in grp_c.iterrows()
    ]

    # disbursements
    df_disb = df[df.apply(lambda r: _is_disbursement(r, measure_col), axis=1)]
    grp_d = df_disb.groupby(recip_col, as_index=False)[value_col].sum()
    grp_d = grp_d.sort_values(value_col, ascending=False).head(10)
    out["disbursements"] = [
        {"country": str(r[recip_col]), "amount": float(r[value_col])}
        for _, r in grp_d.iterrows()
    ]

    return out


def main():
    result = {
        "year": YEAR,
        "updated": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "donors": {},
    }

    for key, donor_name in DONORS.items():
        print(f"Fetching OECD DAC1 for donor: {key} ({donor_name}) year={YEAR} ...")
        result["donors"][key] = fetch_top10_for_donor(donor_name)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Data updated: {OUT_PATH.as_posix()}")

if __name__ == "__main__":
    main()
