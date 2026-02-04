import json
import time
from datetime import datetime
from collections import defaultdict

import requests

YEAR = 2025
OUT_PATH = "data/top10_2025.json"

# Itt a kulcs a te "donor neve" (ami a weben megjelenik),
# az érték pedig az a donor string, amit a Humdata FTS API nagy eséllyel ért.
DONORS = {
    "EU": "European Union",
    "USA": "United States of America",
    "Germany": "Germany",
    "UK": "United Kingdom",
    "Japan": "Japan",
    "France": "France",
    "Canada": "Canada",
    "Sweden": "Sweden",
    "Norway": "Norway",
    "Netherlands": "Netherlands",
}

BASE_URL = "https://api.humdata.org/v1/fts/flows"

# több donor-név variációt próbálunk, ha a fő nem ad vissza adatot
DONOR_ALIASES = {
    "EU": ["European Union", "European Union Institutions", "EU"],
    "USA": ["United States of America", "United States", "USA", "US"],
    "UK": ["United Kingdom", "UK"],
}

def safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def fetch_flows(donor_query: str, year: int):
    # nagyon védett, többféle válaszformát kezel
    params = {
        "year": year,
        "donor": donor_query,
        # nagyobb limit, hogy legyen miből top10-et számolni
        "limit": 1000,
    }
    r = requests.get(BASE_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def parse_and_aggregate(flow_json: dict):
    """
    Kinyeri a recipient/célország neveket és az összegeket (USD),
    majd országonként összeadja.
    """
    totals = defaultdict(float)

    # A Humdata API többféle struktúrát adhat, ezért több helyet is nézünk:
    data = flow_json.get("data")
    if data is None:
        data = flow_json.get("results")
    if data is None:
        data = flow_json.get("items")
    if not isinstance(data, list):
        return totals

    for item in data:
        if not isinstance(item, dict):
            continue

        # ország / destination név - több lehetséges kulcs
        country = (
            safe_get(item, "destination", "name")
            or safe_get(item, "recipient", "name")
            or safe_get(item, "location", "name")
            or item.get("destination")
            or item.get("recipient")
            or item.get("country")
        )

        if isinstance(country, dict):
            country = country.get("name")

        if not isinstance(country, str) or not country.strip():
            continue

        # összeg - több lehetséges kulcs
        amount = (
            item.get("amountUSD")
            or item.get("amount_usd")
            or item.get("amount")
            or safe_get(item, "value", "amountUSD")
            or safe_get(item, "value", "amount")
        )

        try:
            amount = float(amount)
        except Exception:
            continue

        if amount <= 0:
            continue

        totals[country.strip()] += amount

    return totals

def get_top10_for_donor(donor_label: str, year: int):
    candidates = DONOR_ALIASES.get(donor_label, [DONORS[donor_label]])

    best = []
    best_count = 0

    for dq in candidates:
        try:
            raw = fetch_flows(dq, year)
            totals = parse_and_aggregate(raw)

            # top10 (USD -> millió USD)
            top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]
            if len(top) > best_count:
                best_count = len(top)
                best = top

            # ha már van normális mennyiségű adat, nem próbálkozunk tovább
            if best_count >= 8:
                break

            time.sleep(0.2)
        except Exception:
            continue

    # átalakítás a frontended formájára
    out = []
    for country, usd in best:
        out.append({
            "country": country,
            "value": round(usd / 1_000_000, 2)  # millió USD
        })
    return out

def main():
    result = {
        "year": YEAR,
        "updated": datetime.utcnow().isoformat(timespec="microseconds") + "Z",
        "donors": {}
    }

    for donor_label in DONORS.keys():
        result["donors"][donor_label] = get_top10_for_donor(donor_label, YEAR)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Data updated: {OUT_PATH}")

if __name__ == "__main__":
    main()
