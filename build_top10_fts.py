import requests
import json
from datetime import datetime

YEAR = 2025

# Donor kódok az FTS rendszer szerint
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
    "Netherlands": "Netherlands"
}

BASE_URL = "https://api.hpc.tools/v1/public/fts/flow"


def get_top10(donor_name):
    params = {
        "year": YEAR,
        "donor": donor_name
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching {donor_name}: {e}")
        return []

    flows = data.get("data", [])

    # ország + összeg összesítése
    totals = {}
    for item in flows:
        country = item.get("destination", "Unknown")
        amount = float(item.get("amountUSD", 0))
        totals[country] = totals.get(country, 0) + amount

    # TOP10 rendezés
    top10 = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]

    return [
        {"country": country, "amount_usd": round(amount, 2)}
        for country, amount in top10
    ]


def main():
    result = {
        "year": YEAR,
        "updated": datetime.utcnow().isoformat(),
        "donors": {}
    }

    for key, name in DONORS.items():
        print(f"Fetching data for {name}...")
        result["donors"][key] = get_top10(name)

    with open("data/top10_2025.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("Data updated: data/top10_2025.json")


if __name__ == "__main__":
    main()
